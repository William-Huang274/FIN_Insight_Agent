from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EVAL_SET = REPO_ROOT / "eval_sets" / "sec_agent_resume_closeout_eval_v1.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "quality" / "resume_closeout"
DEFAULT_MARKET_EVIDENCE_PATH = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "market"
    / "evidence_packs"
    / "20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl"
)
DEFAULT_MARKET_SNAPSHOT_ID = "20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1"
DEFAULT_MARKET_AS_OF_DATE = "2026-05-22"
DEFAULT_MIXED_10K_10Q_MANIFEST = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "manifests"
    / "sec_tech_primary_mixed_10k_latest_10q_manifest_fy2023_2027.jsonl"
)
DEFAULT_MIXED_10K_10Q_BM25 = (
    REPO_ROOT / "data" / "indexes" / "bm25" / "sec_tech_primary_mixed_10k_latest_10q_fy2023_2027"
)
DEFAULT_MIXED_10K_10Q_OBJECT_BM25 = (
    REPO_ROOT / "data" / "indexes" / "bm25" / "sec_tech_primary_mixed_10k_latest_10q_fy2023_2027_objects"
)
DEFAULT_FULL_SOURCE_MANIFEST = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "manifests"
    / "sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl"
)
DEFAULT_FULL_SOURCE_BM25 = (
    REPO_ROOT / "data" / "indexes" / "bm25" / "sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027"
)
DEFAULT_FULL_SOURCE_OBJECT_BM25 = (
    REPO_ROOT
    / "data"
    / "indexes"
    / "bm25"
    / "sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects"
)

REQUIRED_FULL_SOURCE_FORMS = ("10-K", "10-Q", "8-K")
REQUIRED_FULL_SOURCE_TIERS = (
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
    "market_snapshot",
)
REQUIRED_MARKET_FIELDS = (
    "close_price",
    "market_cap",
    "return_3m",
    "relative_return_vs_benchmark_3m",
    "max_drawdown_3m",
    "volatility_3m",
    "pe_ttm",
    "ev_sales_ttm",
    "latest_10q_filing_return_5d",
)
CRITICAL_LOCAL_CHECKS = {
    "context_state_replay",
    "context_api_smoke",
    "context_managed_dispatch_replay",
    "tool_harness_dispatch_fixtures",
    "unit_contract_tests",
}
MAIN_CHAIN_CASE_CATEGORIES = {
    "full_source_investment_memo",
    "broad_universe_scan",
    "source_boundary_negative_control",
    "management_commentary",
    "market_snapshot_peer_analysis",
}
FULL_SOURCE_REQUIRED_CATEGORIES = {
    "full_source_investment_memo",
    "broad_universe_scan",
    "management_commentary",
}
BROAD_SCAN_TICKERS = ("NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "AMZN", "META", "MU", "INTC", "AMAT", "ADBE", "SNOW")
DEFAULT_CLOSEOUT_YEARS = "2023,2024,2025,2026"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate local SEC-agent self-checks and optional saved full-source run inspection "
            "for first-version closeout readiness."
        )
    )
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET))
    parser.add_argument("--output-path", default="")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--timeout-s", type=int, default=300)
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--skip-planner-eval", action="store_true")
    parser.add_argument("--skip-market-smoke", action="store_true")
    parser.add_argument("--skip-main-chain-case-suite", action="store_true")
    parser.add_argument("--main-chain-case-limit", type=int, default=5)
    parser.add_argument("--skip-context-load-smoke", action="store_true")
    parser.add_argument("--context-load-requests", type=int, default=40)
    parser.add_argument("--context-load-concurrency", type=int, default=4)
    parser.add_argument("--skip-latency-profile", action="store_true")
    parser.add_argument(
        "--latency-profile-case-path",
        default="reports/quality/resume_closeout/market_main_chain_smoke_outputs/20260526_031835_f7b01aec3a/case.jsonl",
    )
    parser.add_argument("--skip-local-subchecks", action="store_true")
    parser.add_argument("--fail-on-blocker", action="store_true")
    parser.add_argument("--require-full-source-artifacts", action="store_true")
    parser.add_argument("--saved-full-source-run-dir", default="")
    parser.add_argument("--mixed-manifest-path", default=str(DEFAULT_MIXED_10K_10Q_MANIFEST))
    parser.add_argument("--mixed-bm25-index-dir", default=str(DEFAULT_MIXED_10K_10Q_BM25))
    parser.add_argument("--mixed-object-bm25-index-dir", default=str(DEFAULT_MIXED_10K_10Q_OBJECT_BM25))
    parser.add_argument("--full-source-manifest-path", default=str(DEFAULT_FULL_SOURCE_MANIFEST))
    parser.add_argument("--full-source-bm25-index-dir", default=str(DEFAULT_FULL_SOURCE_BM25))
    parser.add_argument("--full-source-object-bm25-index-dir", default=str(DEFAULT_FULL_SOURCE_OBJECT_BM25))
    parser.add_argument("--market-evidence-path", default=str(DEFAULT_MARKET_EVIDENCE_PATH))
    parser.add_argument("--market-snapshot-id", default=DEFAULT_MARKET_SNAPSHOT_ID)
    parser.add_argument("--market-as-of-date", default=DEFAULT_MARKET_AS_OF_DATE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    output_path = _default_output_path() if not args.output_path else _repo_path(args.output_path)
    run_root = output_path.parent / output_path.stem
    run_root.mkdir(parents=True, exist_ok=True)
    eval_set = _read_json(_repo_path(args.eval_set)) if _repo_path(args.eval_set).exists() else {}

    checks: list[dict[str, Any]] = []
    checks.append(
        _inspect_source_inventory(
            full_source_manifest_path=_repo_path(args.full_source_manifest_path),
            full_source_bm25_index_dir=_repo_path(args.full_source_bm25_index_dir),
            full_source_object_bm25_index_dir=_repo_path(args.full_source_object_bm25_index_dir),
            mixed_manifest_path=_repo_path(args.mixed_manifest_path),
            mixed_bm25_index_dir=_repo_path(args.mixed_bm25_index_dir),
            mixed_object_bm25_index_dir=_repo_path(args.mixed_object_bm25_index_dir),
            market_evidence_path=_repo_path(args.market_evidence_path),
            require_full_source_artifacts=bool(args.require_full_source_artifacts),
        )
    )
    checks.append(_inspect_saved_full_source_run(_repo_path(args.saved_full_source_run_dir) if args.saved_full_source_run_dir else None))

    if not args.skip_local_subchecks:
        checks.extend(_run_local_subchecks(args=args, run_root=run_root))
    else:
        checks.append(
            _skipped_check(
                check_id="local_subchecks",
                dimension="orchestration",
                reason="disabled_by_cli",
                critical=False,
            )
        )
    if args.skip_main_chain_case_suite:
        checks.append(_skipped_check("main_chain_case_suite_local", "retrieval_coverage_judgment", "disabled_by_cli", critical=False))
    else:
        checks.append(_run_main_chain_case_suite(args=args, eval_set=eval_set, run_root=run_root, timeout_s=args.timeout_s))

    if args.skip_context_load_smoke:
        checks.append(_skipped_check("context_api_small_pressure_local", "p0_state_consistency", "disabled_by_cli", critical=False))
    else:
        checks.append(_run_context_load_smoke(args=args, run_root=run_root, timeout_s=args.timeout_s))

    if args.skip_latency_profile:
        checks.append(_skipped_check("latency_profile_local", "p0_performance_resource", "disabled_by_cli", critical=False))
    else:
        checks.append(_run_latency_profile(args=args, run_root=run_root, timeout_s=args.timeout_s))

    aggregate = _aggregate_checks(checks)
    report = {
        "schema_version": "sec_agent_resume_closeout_readiness_v0.1",
        "run_id": output_path.stem,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(REPO_ROOT.resolve()),
        "eval_set_path": str(_repo_path(args.eval_set).resolve()),
        "eval_set_summary": _eval_set_summary(eval_set),
        "overall_status": aggregate["overall_status"],
        "aggregate": aggregate,
        "p0_readiness": _p0_readiness(checks),
        "checks": checks,
        "assessment_matrix": _assessment_matrix(eval_set, checks),
        "elapsed_sec": round(time.time() - started, 4),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "overall_status": report["overall_status"],
                "blocker_fail_count": aggregate["blocker_fail_count"],
                "warn_count": aggregate["warn_count"],
                "skipped_count": aggregate["skipped_count"],
                "check_count": aggregate["check_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if args.fail_on_blocker and aggregate["blocker_fail_count"] else 0


def _run_local_subchecks(*, args: argparse.Namespace, run_root: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    fixtures_root = run_root / "fixtures"
    reports_root = run_root / "subcheck_reports"
    reports_root.mkdir(parents=True, exist_ok=True)
    common_fixture_args = ["--clean-fixtures"]

    command_specs = [
        {
            "check_id": "context_state_replay",
            "dimension": "session_context",
            "critical": True,
            "summary_path": reports_root / "context_state_replay.json",
            "command": [
                args.python,
                "scripts/evaluate_sec_agent_context_state_replay.py",
                "--fixture-root",
                str(fixtures_root / "context_state_replay"),
                "--output-path",
                str(reports_root / "context_state_replay.json"),
                *common_fixture_args,
            ],
        },
        {
            "check_id": "context_api_smoke",
            "dimension": "request_api_context",
            "critical": True,
            "summary_path": reports_root / "context_api_smoke.json",
            "command": [
                args.python,
                "scripts/evaluate_sec_agent_context_api_smoke.py",
                "--fixture-root",
                str(fixtures_root / "context_api_smoke"),
                "--output-path",
                str(reports_root / "context_api_smoke.json"),
                "--controller-backend",
                "heuristic",
                *common_fixture_args,
            ],
        },
        {
            "check_id": "context_managed_dispatch_replay",
            "dimension": "tool_call_dispatch_context_update",
            "critical": True,
            "summary_path": reports_root / "context_managed_dispatch_replay.json",
            "command": [
                args.python,
                "scripts/evaluate_sec_agent_context_managed_dispatch_replay.py",
                "--fixture-root",
                str(fixtures_root / "context_managed_dispatch_replay"),
                "--output-path",
                str(reports_root / "context_managed_dispatch_replay.json"),
                "--controller-backend",
                "heuristic",
                *common_fixture_args,
            ],
        },
        {
            "check_id": "tool_harness_dispatch_fixtures",
            "dimension": "tool_harness_artifact_access",
            "critical": True,
            "summary_path": reports_root / "tool_harness_dispatch_fixtures.json",
            "command": [
                args.python,
                "scripts/evaluate_sec_agent_tool_harness_dispatch_fixtures.py",
                "--fixture-root",
                str(fixtures_root / "tool_harness_dispatch_fixtures"),
                "--output-path",
                str(reports_root / "tool_harness_dispatch_fixtures.json"),
                *common_fixture_args,
            ],
        },
    ]
    for spec in command_specs:
        checks.append(_run_command_check(spec=spec, timeout_s=args.timeout_s))

    if args.skip_pytest:
        checks.append(_skipped_check("unit_contract_tests", "source_contracts", "disabled_by_cli", critical=True))
    else:
        checks.append(
            _run_command_check(
                spec={
                    "check_id": "unit_contract_tests",
                    "dimension": "source_contracts",
                    "critical": True,
                    "command": [
                        args.python,
                        "-m",
                        "pytest",
                        "tests/test_market_snapshot_fixture.py",
                        "tests/test_sec_agent_10q_source_contract.py",
                        "tests/test_build_sec_mixed_latest_manifest.py",
                        "-q",
                    ],
                },
                timeout_s=args.timeout_s,
            )
        )

    if args.skip_planner_eval:
        checks.append(_skipped_check("planner_contract_eval_local", "planner_contract", "disabled_by_cli", critical=False))
    else:
        checks.append(_run_planner_contract_eval(args=args, reports_root=reports_root, timeout_s=args.timeout_s))

    if args.skip_market_smoke:
        checks.append(_skipped_check("market_main_chain_smoke_local", "retrieval_coverage_judgment", "disabled_by_cli", critical=False))
    else:
        checks.append(_run_market_main_chain_smoke(args=args, timeout_s=args.timeout_s))
    return checks


def _run_planner_contract_eval(*, args: argparse.Namespace, reports_root: Path, timeout_s: int) -> dict[str, Any]:
    eval_path = REPO_ROOT / "eval_sets" / "sec_agent_resume_closeout_planner_eval_v1.jsonl"
    contracts_path = reports_root / "resume_closeout_planner_contracts_heuristic.jsonl"
    report_path = reports_root / "resume_closeout_planner_eval_heuristic.json"
    if not eval_path.exists():
        return _skipped_check("planner_contract_eval_local", "planner_contract", "missing_eval_set", critical=False)
    manifest_path = _repo_path(args.mixed_manifest_path)
    if not manifest_path.exists():
        return _skipped_check("planner_contract_eval_local", "planner_contract", "missing_planner_manifest", critical=False)
    env = dict(os.environ)
    env.setdefault("SEC_AGENT_SOURCE_POLICY", "SEC_PRIMARY_MIXED_RECENT")
    generate = _run_subprocess(
        [
            args.python,
            "scripts/run_sec_free_query_planner_eval.py",
            "--eval-path",
            str(eval_path),
            "--output-path",
            str(contracts_path),
            "--query-planner",
            "heuristic",
            "--manifest-path",
            str(manifest_path),
            "--bm25-index-dir",
            str(_repo_path(args.mixed_bm25_index_dir)),
            "--object-bm25-index-dir",
            str(_repo_path(args.mixed_object_bm25_index_dir)),
            "--quiet",
        ],
        timeout_s=timeout_s,
        env=env,
    )
    evaluate = _run_subprocess(
        [
            args.python,
            "scripts/evaluate_sec_free_query_planner.py",
            "--eval-path",
            str(eval_path),
            "--contracts-path",
            str(contracts_path),
            "--output-path",
            str(report_path),
        ],
        timeout_s=timeout_s,
        env=env,
    )
    report = _read_json(report_path) if report_path.exists() else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    status = "pass" if summary.get("meets_step1_acceptance") else "warn"
    return {
        "check_id": "planner_contract_eval_local",
        "dimension": "planner_contract",
        "status": status,
        "critical": False,
        "reason": "heuristic_local_diagnostic" if status == "warn" else "",
        "commands": [generate["command"], evaluate["command"]],
        "returncodes": [generate["returncode"], evaluate["returncode"]],
        "summary_path": str(report_path.resolve()),
        "summary": summary,
        "stdout_tail": "\n".join([generate.get("stdout_tail", ""), evaluate.get("stdout_tail", "")]).strip()[-3000:],
        "stderr_tail": "\n".join([generate.get("stderr_tail", ""), evaluate.get("stderr_tail", "")]).strip()[-3000:],
    }


def _run_market_main_chain_smoke(*, args: argparse.Namespace, timeout_s: int) -> dict[str, Any]:
    required_paths = {
        "manifest": _repo_path(args.mixed_manifest_path),
        "bm25_index": _repo_path(args.mixed_bm25_index_dir),
        "object_bm25_index": _repo_path(args.mixed_object_bm25_index_dir),
        "market_evidence": _repo_path(args.market_evidence_path),
    }
    missing = {name: str(path) for name, path in required_paths.items() if not path.exists()}
    if missing:
        return {
            "check_id": "market_main_chain_smoke_local",
            "dimension": "retrieval_coverage_judgment",
            "status": "skipped",
            "critical": False,
            "reason": "missing_required_local_artifacts",
            "missing": missing,
        }
    command = [
        args.python,
        "scripts/market/60_smoke_market_snapshot_main_chain.py",
        "--prompt",
        (
            "结合SEC财报和最近三个月market snapshot，比较NVDA、AMD、MSFT、AMZN、GOOGL"
            "的AI相关基本面、最新10-Q市场反应和估值是否一致，并标明证据边界。"
        ),
        "--tickers",
        "NVDA,AMD,MSFT,AMZN,GOOGL",
        "--years",
        "2023,2024,2025,2026",
        "--manifest-path",
        str(required_paths["manifest"]),
        "--bm25-index-dir",
        str(required_paths["bm25_index"]),
        "--object-bm25-index-dir",
        str(required_paths["object_bm25_index"]),
        "--market-evidence-path",
        str(required_paths["market_evidence"]),
        "--market-snapshot-id",
        args.market_snapshot_id,
        "--market-as-of-date",
        args.market_as_of_date,
        "--output-root",
        "reports/quality/resume_closeout/market_main_chain_smoke_outputs",
        "--evidence-top-k",
        "4",
        "--object-top-k",
        "4",
        "--max-context-rows",
        "150",
        "--ledger-max-rows",
        "90",
    ]
    completed = _run_subprocess(command, timeout_s=timeout_s)
    summary = _parse_json_object(completed.get("stdout_tail", "")) or {}
    status = "pass" if completed["returncode"] == 0 and summary.get("status") == "pass" else "warn"
    return {
        "check_id": "market_main_chain_smoke_local",
        "dimension": "retrieval_coverage_judgment",
        "status": status,
        "critical": False,
        "reason": "" if status == "pass" else "diagnostic_smoke_not_green",
        "command": completed["command"],
        "returncode": completed["returncode"],
        "summary": summary,
        "stdout_tail": completed.get("stdout_tail", ""),
        "stderr_tail": completed.get("stderr_tail", ""),
    }


def _run_main_chain_case_suite(
    *,
    args: argparse.Namespace,
    eval_set: dict[str, Any],
    run_root: Path,
    timeout_s: int,
) -> dict[str, Any]:
    cases = [
        case
        for case in (eval_set.get("cases") or [])
        if isinstance(case, dict) and str(case.get("category") or "") in MAIN_CHAIN_CASE_CATEGORIES
    ]
    if args.main_chain_case_limit > 0:
        cases = cases[: args.main_chain_case_limit]
    if not cases:
        return _skipped_check("main_chain_case_suite_local", "retrieval_coverage_judgment", "missing_eval_cases", critical=False)

    case_results: list[dict[str, Any]] = []
    for case in cases:
        case_results.append(_run_one_main_chain_case(args=args, case=case, run_root=run_root, timeout_s=timeout_s))

    executed = [row for row in case_results if row.get("status") != "skipped"]
    failures = [row for row in executed if row.get("status") != "pass"]
    skipped = [row for row in case_results if row.get("status") == "skipped"]
    status = "pass" if executed and not failures and not skipped else ("fail" if failures else "warn")
    return {
        "check_id": "main_chain_case_suite_local",
        "dimension": "retrieval_coverage_judgment",
        "status": status,
        "critical": False,
        "reason": "some_cases_failed_or_skipped" if status != "pass" else "",
        "case_count": len(case_results),
        "executed_count": len(executed),
        "skipped_count": len(skipped),
        "failure_count": len(failures),
        "case_results": case_results,
    }


def _run_one_main_chain_case(
    *,
    args: argparse.Namespace,
    case: dict[str, Any],
    run_root: Path,
    timeout_s: int,
) -> dict[str, Any]:
    category = str(case.get("category") or "")
    needs_full_source = category in FULL_SOURCE_REQUIRED_CATEGORIES
    manifest_path = _repo_path(args.full_source_manifest_path if needs_full_source else args.mixed_manifest_path)
    bm25_index_dir = _repo_path(args.full_source_bm25_index_dir if needs_full_source else args.mixed_bm25_index_dir)
    object_bm25_index_dir = _repo_path(args.full_source_object_bm25_index_dir if needs_full_source else args.mixed_object_bm25_index_dir)
    required_paths = {
        "manifest": manifest_path,
        "bm25_index": bm25_index_dir,
        "object_bm25_index": object_bm25_index_dir,
        "market_evidence": _repo_path(args.market_evidence_path),
    }
    missing = {name: str(path) for name, path in required_paths.items() if not path.exists()}
    if missing:
        return {
            "case_id": case.get("case_id"),
            "category": category,
            "status": "skipped",
            "reason": "missing_required_local_artifacts",
            "needs_full_source": needs_full_source,
            "missing": missing,
        }

    tickers = _case_tickers(case)
    command = [
        args.python,
        "scripts/market/60_smoke_market_snapshot_main_chain.py",
        "--prompt",
        str(case.get("query") or ""),
        "--tickers",
        ",".join(tickers),
        "--years",
        DEFAULT_CLOSEOUT_YEARS,
        "--manifest-path",
        str(manifest_path),
        "--bm25-index-dir",
        str(bm25_index_dir),
        "--object-bm25-index-dir",
        str(object_bm25_index_dir),
        "--market-evidence-path",
        str(required_paths["market_evidence"]),
        "--market-snapshot-id",
        args.market_snapshot_id,
        "--market-as-of-date",
        args.market_as_of_date,
        "--output-root",
        str(run_root / "main_chain_case_suite"),
        "--evidence-top-k",
        "4",
        "--object-top-k",
        "4",
        "--max-context-rows",
        "160",
        "--ledger-max-rows",
        "100",
    ]
    completed = _run_subprocess(command, timeout_s=timeout_s)
    summary = _parse_json_object(completed.get("stdout_tail", "")) or {}
    negative_market_control = category == "source_boundary_negative_control"
    source_boundary_pass = not negative_market_control or (
        summary.get("market_requested") is False and int(summary.get("market_context_row_count") or 0) == 0
    )
    status = "pass" if completed["returncode"] == 0 and summary.get("status") == "pass" and source_boundary_pass else "fail"
    return {
        "case_id": case.get("case_id"),
        "category": category,
        "status": status,
        "reason": "" if status == "pass" else "main_chain_case_not_green",
        "needs_full_source": needs_full_source,
        "tickers": tickers,
        "command": completed["command"],
        "returncode": completed["returncode"],
        "summary": summary,
        "source_boundary_pass": source_boundary_pass,
        "stdout_tail": completed.get("stdout_tail", ""),
        "stderr_tail": completed.get("stderr_tail", ""),
    }


def _run_context_load_smoke(*, args: argparse.Namespace, run_root: Path, timeout_s: int) -> dict[str, Any]:
    output_path = run_root / "subcheck_reports" / "context_api_small_pressure.json"
    command = [
        args.python,
        "scripts/benchmark_sec_agent_context_api.py",
        "--fixture-root",
        str(run_root / "fixtures" / "context_api_small_pressure"),
        "--output-path",
        str(output_path),
        "--requests",
        str(max(args.context_load_requests, 1)),
        "--concurrency",
        str(max(args.context_load_concurrency, 1)),
        "--warmup-requests",
        "5",
        "--workload",
        "mixed",
        "--controller-backend",
        "heuristic",
        "--clean-fixtures",
    ]
    return _run_command_check(
        spec={
            "check_id": "context_api_small_pressure_local",
            "dimension": "p0_state_consistency",
            "critical": False,
            "summary_path": output_path,
            "command": command,
        },
        timeout_s=timeout_s,
    )


def _run_latency_profile(*, args: argparse.Namespace, run_root: Path, timeout_s: int) -> dict[str, Any]:
    case_path = _repo_path(args.latency_profile_case_path)
    if not case_path.exists():
        return {
            "check_id": "latency_profile_local",
            "dimension": "p0_performance_resource",
            "status": "skipped",
            "critical": False,
            "reason": "missing_latency_profile_case",
            "case_path": str(case_path),
        }
    output_path = run_root / "subcheck_reports" / "latency_profile.json"
    command = [
        args.python,
        "scripts/evaluate_sec_agent_latency_profile.py",
        "--case-path",
        str(case_path),
        "--output-path",
        str(output_path),
    ]
    completed = _run_subprocess(command, timeout_s=timeout_s)
    summary = _read_json(output_path) if output_path.exists() else {}
    status = "pass" if completed["returncode"] == 0 and str(summary.get("status") or "") in {"pass", "warn"} else "fail"
    return {
        "check_id": "latency_profile_local",
        "dimension": "p0_performance_resource",
        "status": status,
        "critical": False,
        "reason": "" if status == "pass" else "latency_profile_failed",
        "command": completed["command"],
        "returncode": completed["returncode"],
        "summary_path": str(output_path.resolve()),
        "summary": {
            "status": summary.get("status"),
            "reasons": summary.get("reasons") or [],
            "retrieval": summary.get("retrieval") or {},
            "runtime_ledger": summary.get("runtime_ledger") or {},
            "coverage_matrix": summary.get("coverage_matrix") or {},
        },
        "stdout_tail": completed.get("stdout_tail", ""),
        "stderr_tail": completed.get("stderr_tail", ""),
    }


def _run_command_check(*, spec: dict[str, Any], timeout_s: int) -> dict[str, Any]:
    completed = _run_subprocess(spec["command"], timeout_s=timeout_s)
    summary_path = spec.get("summary_path")
    summary = _read_json(summary_path) if summary_path and Path(summary_path).exists() else {}
    all_pass = _summary_passed(summary) if summary else completed["returncode"] == 0
    return {
        "check_id": spec["check_id"],
        "dimension": spec["dimension"],
        "status": "pass" if completed["returncode"] == 0 and all_pass else "fail",
        "critical": bool(spec.get("critical")),
        "command": completed["command"],
        "returncode": completed["returncode"],
        "summary_path": str(Path(summary_path).resolve()) if summary_path else "",
        "summary": _compact_summary(summary),
        "stdout_tail": completed.get("stdout_tail", ""),
        "stderr_tail": completed.get("stderr_tail", ""),
    }


def _run_subprocess(command: list[str], *, timeout_s: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=env,
        )
        return {
            "command": command,
            "returncode": proc.returncode,
            "elapsed_sec": round(time.time() - started, 4),
            "stdout_tail": (proc.stdout or "")[-3000:],
            "stderr_tail": (proc.stderr or "")[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": 124,
            "elapsed_sec": round(time.time() - started, 4),
            "stdout_tail": (exc.stdout or "")[-3000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-3000:] if isinstance(exc.stderr, str) else "",
            "timeout_s": timeout_s,
        }


def _inspect_source_inventory(
    *,
    full_source_manifest_path: Path,
    full_source_bm25_index_dir: Path,
    full_source_object_bm25_index_dir: Path,
    mixed_manifest_path: Path,
    mixed_bm25_index_dir: Path,
    mixed_object_bm25_index_dir: Path,
    market_evidence_path: Path,
    require_full_source_artifacts: bool,
) -> dict[str, Any]:
    full_manifest = _manifest_summary(full_source_manifest_path)
    mixed_manifest = _manifest_summary(mixed_manifest_path)
    market_summary = _market_evidence_summary(market_evidence_path)
    path_presence = {
        "full_source_manifest": full_source_manifest_path.exists(),
        "full_source_bm25_index": full_source_bm25_index_dir.exists(),
        "full_source_object_bm25_index": full_source_object_bm25_index_dir.exists(),
        "mixed_10k_10q_manifest": mixed_manifest_path.exists(),
        "mixed_10k_10q_bm25_index": mixed_bm25_index_dir.exists(),
        "mixed_10k_10q_object_bm25_index": mixed_object_bm25_index_dir.exists(),
        "market_evidence": market_evidence_path.exists(),
    }
    full_forms = set(full_manifest.get("form_counts") or {})
    market_fields = set(market_summary.get("field_counts") or {})
    missing_full_forms = sorted(set(REQUIRED_FULL_SOURCE_FORMS) - full_forms)
    missing_market_fields = sorted(set(REQUIRED_MARKET_FIELDS) - market_fields)
    missing_full_paths = [key for key, exists in path_presence.items() if key.startswith("full_source") and not exists]
    blocking = bool(require_full_source_artifacts and (missing_full_paths or missing_full_forms))
    warn = bool((missing_full_paths or missing_full_forms or missing_market_fields) and not blocking)
    return {
        "check_id": "source_inventory_artifacts",
        "dimension": "source_inventory",
        "status": "fail" if blocking else ("warn" if warn else "pass"),
        "critical": bool(require_full_source_artifacts),
        "reason": "missing_full_source_artifacts" if (missing_full_paths or missing_full_forms) else "",
        "path_presence": path_presence,
        "paths": {
            "full_source_manifest": str(full_source_manifest_path),
            "full_source_bm25_index": str(full_source_bm25_index_dir),
            "full_source_object_bm25_index": str(full_source_object_bm25_index_dir),
            "mixed_10k_10q_manifest": str(mixed_manifest_path),
            "market_evidence": str(market_evidence_path),
        },
        "full_source_manifest_summary": full_manifest,
        "mixed_10k_10q_manifest_summary": mixed_manifest,
        "market_evidence_summary": market_summary,
        "missing_full_source_paths": missing_full_paths,
        "missing_full_source_forms": missing_full_forms,
        "missing_market_fields": missing_market_fields,
    }


def _inspect_saved_full_source_run(run_dir: Path | None) -> dict[str, Any]:
    if run_dir is None:
        return _skipped_check(
            check_id="saved_full_source_deepseek_run",
            dimension="model_synthesis_post_gates",
            reason="not_provided",
            critical=False,
        )
    if not run_dir.exists():
        return {
            "check_id": "saved_full_source_deepseek_run",
            "dimension": "model_synthesis_post_gates",
            "status": "fail",
            "critical": True,
            "reason": "run_dir_not_found",
            "run_dir": str(run_dir),
        }
    paths = {
        "state": run_dir / "sec_agent_state.json",
        "coverage": run_dir / "runtime_evidence_coverage_matrix.json",
        "ledger": run_dir / "runtime_exact_value_ledger.json",
        "judgment_plan": run_dir / "runtime_judgment_plan.json",
        "agent_outputs": run_dir / "qwen" / "agent_outputs.jsonl",
        "rendered_answer": run_dir / "qwen" / "rendered_answer.md",
        "gate_summary": run_dir / "post_gates" / "sec_benchmark_post_gates_summary.json",
        "market_context": run_dir / "market_snapshot_context_rows.jsonl",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    state = _read_json(paths["state"]) if paths["state"].exists() else {}
    coverage = _read_json(paths["coverage"]) if paths["coverage"].exists() else {}
    ledger = _read_json(paths["ledger"]) if paths["ledger"].exists() else {}
    gates = _read_json(paths["gate_summary"]) if paths["gate_summary"].exists() else {}
    agent_rows = _read_jsonl(paths["agent_outputs"]) if paths["agent_outputs"].exists() else []
    rendered_text = paths["rendered_answer"].read_text(encoding="utf-8", errors="replace") if paths["rendered_answer"].exists() else ""
    gate_fail_keys = [key for key, value in gates.items() if key.endswith("_gate_pass") and value is False]
    coverage_summary = coverage.get("summary") if isinstance(coverage.get("summary"), dict) else {}
    market_coverage = coverage.get("market_snapshot_coverage") if isinstance(coverage.get("market_snapshot_coverage"), dict) else {}
    agent_statuses = Counter(str(row.get("answer_status") or row.get("status") or "") for row in agent_rows)
    fallback_answer_count = sum(count for status, count in agent_statuses.items() if "fallback" in status)
    ledger_rows = ledger.get("rows") if isinstance(ledger.get("rows"), list) else []
    market_rows = _read_jsonl(paths["market_context"]) if paths["market_context"].exists() else []
    rendered_boundary_labels = {
        "mentions_10q": "10-Q" in rendered_text or "未经审计" in rendered_text,
        "mentions_8k": "8-K" in rendered_text or "earnings release" in rendered_text,
        "mentions_market_snapshot": "market_snapshot" in rendered_text or "market snapshot" in rendered_text,
        "mentions_as_of_date": "as_of_date" in rendered_text or "as of" in rendered_text or "截至" in rendered_text,
    }
    has_required_runtime = not missing
    gates_green = bool(gates) and not gate_fail_keys
    coverage_green = bool(coverage_summary.get("primary_task_support_complete", coverage_summary.get("coverage_complete", False)))
    market_green = bool(market_coverage.get("market_snapshot_support_complete", bool(market_rows)))
    no_fallback = fallback_answer_count == 0
    status = "pass" if has_required_runtime and gates_green and coverage_green and market_green and no_fallback else "fail"
    return {
        "check_id": "saved_full_source_deepseek_run",
        "dimension": "model_synthesis_post_gates",
        "status": status,
        "critical": True,
        "reason": "" if status == "pass" else "saved_run_not_green",
        "run_dir": str(run_dir),
        "missing_artifacts": missing,
        "state": {
            "run_id": state.get("run_id"),
            "status": state.get("status"),
            "source_policy": state.get("source_policy"),
            "selected_tickers": state.get("selected_tickers") or [],
            "selected_years": state.get("selected_years") or [],
            "total_elapsed_sec": (state.get("metadata") or {}).get("total_elapsed_sec"),
            "stage_statuses": {item.get("name"): item.get("status") for item in state.get("stages") or [] if isinstance(item, dict)},
        },
        "coverage_summary": {
            "coverage_complete": coverage_summary.get("coverage_complete"),
            "primary_task_support_complete": coverage_summary.get("primary_task_support_complete"),
            "answer_status": coverage_summary.get("answer_status"),
            "context_row_count": coverage_summary.get("context_row_count"),
            "ledger_row_count": coverage_summary.get("ledger_row_count"),
        },
        "market_snapshot_coverage": market_coverage,
        "gate_fail_keys": gate_fail_keys,
        "gate_pass_count": sum(1 for key, value in gates.items() if key.endswith("_gate_pass") and value is True),
        "agent_statuses": dict(agent_statuses),
        "fallback_answer_count": fallback_answer_count,
        "ledger_row_count": len(ledger_rows),
        "market_context_row_count": len(market_rows),
        "rendered_boundary_labels": rendered_boundary_labels,
    }


def _aggregate_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(str(check.get("status") or "") for check in checks)
    blocker_failures = [
        check
        for check in checks
        if check.get("critical") and str(check.get("status") or "") == "fail"
    ]
    warn_count = statuses.get("warn", 0)
    skipped_count = statuses.get("skipped", 0)
    if blocker_failures:
        overall_status = "fail"
    elif warn_count or skipped_count:
        overall_status = "warn"
    else:
        overall_status = "pass"
    by_dimension: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for check in checks:
        by_dimension[str(check.get("dimension") or "unknown")].append(check)
    dimension_statuses = {
        dimension: _dimension_status(rows)
        for dimension, rows in sorted(by_dimension.items())
    }
    return {
        "overall_status": overall_status,
        "check_count": len(checks),
        "status_counts": dict(sorted(statuses.items())),
        "blocker_fail_count": len(blocker_failures),
        "blocker_failures": [
            {
                "check_id": check.get("check_id"),
                "dimension": check.get("dimension"),
                "reason": check.get("reason"),
                "returncode": check.get("returncode"),
            }
            for check in blocker_failures
        ],
        "warn_count": warn_count,
        "skipped_count": skipped_count,
        "dimension_statuses": dimension_statuses,
        "critical_checks": sorted(CRITICAL_LOCAL_CHECKS),
    }


def _dimension_status(rows: list[dict[str, Any]]) -> str:
    statuses = [str(row.get("status") or "") for row in rows]
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    if statuses and all(status == "skipped" for status in statuses):
        return "skipped"
    if "skipped" in statuses:
        return "warn"
    return "pass"


def _assessment_matrix(eval_set: dict[str, Any], checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    check_by_dimension: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for check in checks:
        check_by_dimension[str(check.get("dimension") or "unknown")].append(check)
    matrix = []
    for item in eval_set.get("acceptance_dimensions") or []:
        if not isinstance(item, dict):
            continue
        dimension_id = str(item.get("dimension_id") or "")
        rows = check_by_dimension.get(dimension_id, [])
        matrix.append(
            {
                "dimension_id": dimension_id,
                "critical": bool(item.get("critical")),
                "status": _dimension_status(rows) if rows else "unmapped",
                "mapped_checks": [row.get("check_id") for row in rows],
                "acceptance": item.get("acceptance") or [],
            }
        )
    return matrix


def _eval_set_summary(eval_set: dict[str, Any]) -> dict[str, Any]:
    cases = [case for case in eval_set.get("cases") or [] if isinstance(case, dict)]
    dimensions = [item for item in eval_set.get("acceptance_dimensions") or [] if isinstance(item, dict)]
    categories = Counter(str(case.get("category") or "") for case in cases)
    return {
        "schema_version": eval_set.get("schema_version"),
        "case_count": len(cases),
        "dimension_count": len(dimensions),
        "categories": dict(sorted(categories.items())),
        "case_ids": [case.get("case_id") for case in cases],
    }


def _p0_readiness(checks: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(check.get("check_id") or ""): check for check in checks}
    source_inventory = by_id.get("source_inventory_artifacts") or {}
    saved_run = by_id.get("saved_full_source_deepseek_run") or {}
    latency = by_id.get("latency_profile_local") or {}
    load = by_id.get("context_api_small_pressure_local") or {}
    state_replay = by_id.get("context_state_replay") or {}
    dispatch_replay = by_id.get("context_managed_dispatch_replay") or {}
    main_chain_suite = by_id.get("main_chain_case_suite_local") or {}
    p0_items = [
        {
            "item_id": "p0_performance_resource",
            "status": _p0_item_status([latency]),
            "evidence_checks": ["latency_profile_local"],
            "note": "Tracks BM25/ObjectBM25 init/search, candidate generation, cached ledger, market attach, and coverage elapsed time when local artifacts exist.",
        },
        {
            "item_id": "p0_stage_timing_observability",
            "status": _p0_stage_timing_status(saved_run),
            "evidence_checks": ["saved_full_source_deepseek_run"],
            "note": "Requires a saved real full-source run to prove stage elapsed_ms/run_performance/run_data_fingerprint on production-like artifacts.",
        },
        {
            "item_id": "p0_data_index_versioning",
            "status": _p0_source_status(source_inventory),
            "evidence_checks": ["source_inventory_artifacts"],
            "note": "Checks presence and coverage summaries for 10-K, latest 10-Q, 8-K, market evidence, and index directories; digest parity still depends on saved run fingerprints.",
        },
        {
            "item_id": "p0_concurrency_state_consistency",
            "status": _p0_item_status([load, state_replay, dispatch_replay]),
            "evidence_checks": ["context_api_small_pressure_local", "context_state_replay", "context_managed_dispatch_replay"],
            "note": "Validates single-process request lock/load behavior, session isolation, active answer recovery, and dispatch-driven context updates.",
        },
        {
            "item_id": "p0_failure_recovery",
            "status": _p0_item_status([state_replay, dispatch_replay]),
            "evidence_checks": ["context_state_replay", "context_managed_dispatch_replay"],
            "note": "Fixture-backed resume checks cover partial artifact states and no-rerun follow-up tools; true stage-level rerun from a real partial run remains a separate cloud validation.",
        },
        {
            "item_id": "p0_multicase_chain_stability",
            "status": _p0_item_status([main_chain_suite]),
            "evidence_checks": ["main_chain_case_suite_local"],
            "note": "Runs multiple query categories through planner contract, retrieval, market attach, ledger, coverage, and Judgment Plan without LLM synthesis.",
        },
    ]
    status_counts = Counter(item["status"] for item in p0_items)
    if status_counts.get("fail"):
        overall = "fail"
    elif status_counts.get("warn") or status_counts.get("skipped"):
        overall = "warn"
    else:
        overall = "pass"
    return {
        "overall_status": overall,
        "status_counts": dict(sorted(status_counts.items())),
        "items": p0_items,
    }


def _p0_item_status(checks: list[dict[str, Any]]) -> str:
    statuses = [str(check.get("status") or "skipped") for check in checks if check]
    if not statuses:
        return "skipped"
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses or "skipped" in statuses:
        return "warn"
    return "pass"


def _p0_stage_timing_status(saved_run: dict[str, Any]) -> str:
    if not saved_run or saved_run.get("status") == "skipped":
        return "skipped"
    if saved_run.get("status") == "fail":
        return "fail"
    state = saved_run.get("state") if isinstance(saved_run.get("state"), dict) else {}
    stage_statuses = state.get("stage_statuses") if isinstance(state.get("stage_statuses"), dict) else {}
    return "pass" if stage_statuses else "warn"


def _p0_source_status(source_inventory: dict[str, Any]) -> str:
    if not source_inventory:
        return "skipped"
    if source_inventory.get("status") == "fail":
        return "fail"
    missing = (
        source_inventory.get("missing_full_source_paths")
        or source_inventory.get("missing_full_source_forms")
        or source_inventory.get("missing_market_fields")
    )
    if missing or source_inventory.get("status") == "warn":
        return "warn"
    return "pass"


def _case_tickers(case: dict[str, Any]) -> list[str]:
    tickers = case.get("expected_tickers") if isinstance(case.get("expected_tickers"), list) else []
    if not tickers:
        tickers = _tickers_from_text(str(case.get("query") or ""))
    if not tickers and str(case.get("category") or "") == "broad_universe_scan":
        tickers = list(BROAD_SCAN_TICKERS)
    return _unique_upper(tickers or list(BROAD_SCAN_TICKERS[:5]))


def _tickers_from_text(text: str) -> list[str]:
    known = set(BROAD_SCAN_TICKERS) | {"JPM", "V", "JNJ", "LLY", "CAT", "GE", "WMT", "PG", "XOM", "CVX"}
    upper = str(text or "").upper()
    return [ticker for ticker in sorted(known) if ticker in upper]


def _unique_upper(values: list[Any]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip().upper()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _manifest_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    rows = _read_jsonl(path)
    form_counts = Counter(_normalize_form(row.get("form_type") or row.get("form") or row.get("source_type")) for row in rows)
    source_tiers = Counter(str(row.get("source_tier") or "") for row in rows)
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    years = sorted({_safe_int(row.get("fiscal_year") or row.get("document_fiscal_year_focus") or row.get("year")) for row in rows} - {None})
    periods = Counter(str(row.get("period_role") or row.get("fiscal_period") or row.get("period_type") or "") for row in rows)
    return {
        "exists": True,
        "path": str(path),
        "row_count": len(rows),
        "ticker_count": len(tickers),
        "tickers_sample": tickers[:12],
        "years": years,
        "form_counts": dict(sorted((key, value) for key, value in form_counts.items() if key)),
        "source_tier_counts": dict(sorted((key, value) for key, value in source_tiers.items() if key)),
        "period_counts": dict(sorted((key, value) for key, value in periods.items() if key)),
    }


def _market_evidence_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    rows = _read_jsonl(path)
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    snapshots = Counter(str(row.get("snapshot_id") or "") for row in rows)
    as_of_dates = Counter(str(row.get("as_of_date") or "") for row in rows)
    providers = Counter(str(row.get("provider") or "") for row in rows)
    field_counts: Counter[str] = Counter()
    valuation_non_null: Counter[str] = Counter()
    for row in rows:
        for ref in row.get("field_refs") or []:
            if isinstance(ref, dict) and ref.get("field_name"):
                field_counts[str(ref["field_name"])] += 1
                if ref.get("value") is not None and str(ref.get("field_name") or "") in {"pe_ttm", "ev_sales_ttm", "ev_ebitda_ttm"}:
                    valuation_non_null[str(ref["field_name"])] += 1
    return {
        "exists": True,
        "path": str(path),
        "row_count": len(rows),
        "ticker_count": len(tickers),
        "tickers_sample": tickers[:12],
        "snapshot_ids": dict(sorted((key, value) for key, value in snapshots.items() if key)),
        "as_of_dates": dict(sorted((key, value) for key, value in as_of_dates.items() if key)),
        "providers": dict(sorted((key, value) for key, value in providers.items() if key)),
        "field_counts": dict(sorted(field_counts.items())),
        "valuation_non_null_counts": dict(sorted(valuation_non_null.items())),
    }


def _summary_passed(summary: dict[str, Any]) -> bool:
    if not summary:
        return False
    for key in ("all_pass", "can_enter_gate"):
        if key in summary:
            return bool(summary.get(key))
    if "summary" in summary and isinstance(summary["summary"], dict):
        return _summary_passed(summary["summary"])
    return False


def _compact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return {}
    keys = (
        "run_id",
        "case_count",
        "pass_count",
        "passed_count",
        "failed_count",
        "failure_count",
        "all_pass",
        "controller_backend",
        "scenario_count",
        "turn_count",
        "tool_pass_count",
        "arg_pass_count",
        "snapshot_pass_count",
        "dispatch_pass_count",
        "context_update_pass_count",
    )
    compact = {key: summary.get(key) for key in keys if key in summary}
    if "summary" in summary and isinstance(summary["summary"], dict):
        compact["summary"] = summary["summary"]
    return compact


def _skipped_check(check_id: str, dimension: str, reason: str, critical: bool) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "dimension": dimension,
        "status": "skipped",
        "critical": bool(critical),
        "reason": reason,
    }


def _parse_json_object(text: str) -> dict[str, Any] | None:
    text = str(text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = text.rfind("{")
        if start >= 0:
            try:
                parsed = json.loads(text[start:])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    if not Path(path).exists():
        return rows
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _default_output_path() -> Path:
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_resume_closeout_readiness_local_v1"
    return DEFAULT_OUTPUT_DIR / f"{run_id}.json"


def _normalize_form(value: Any) -> str:
    return str(value or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q").replace("8K", "8-K")


def _safe_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
