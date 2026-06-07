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
