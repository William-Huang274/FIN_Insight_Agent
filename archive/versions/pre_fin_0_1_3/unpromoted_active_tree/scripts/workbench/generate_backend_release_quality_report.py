from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "quality" / "workbench_release"
PASS_STATES = {"pass", "passed", "success", "successful", "completed"}
FAIL_STATES = {"fail", "failed", "failure", "error", "cancelled", "timed_out", "timedout"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a backend release-quality report from Workbench CI and pressure artifacts."
    )
    parser.add_argument("--pressure-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-id", default="")
    parser.add_argument(
        "--validation",
        action="append",
        default=[],
        help="Validation record in 'name|status|detail' form. Repeatable.",
    )
    parser.add_argument("--checks-json", type=Path, default=None, help="Optional gh pr checks JSON output.")
    parser.add_argument("--fetch-pr-checks", action="store_true", help="Fetch GitHub PR checks with gh.")
    parser.add_argument("--repo", default="William-Huang274/FIN_Insight_Agent")
    parser.add_argument("--pr-number", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report_id = args.report_id or f"{_timestamp()}_workbench_backend_release_quality"
    checks = _load_checks(args)
    validations = [parse_validation(raw) for raw in args.validation]
    report = build_release_quality_report(
        pressure_summary_path=args.pressure_summary,
        report_id=report_id,
        validations=validations,
        ci_checks=checks,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{report_id}.json"
    md_path = args.output_dir / f"{report_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "report_id": report_id,
                "status": report["overall_status"],
                "markdown_path": str(md_path),
                "json_path": str(json_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["overall_status"] in {"pass", "review"} else 1


def parse_validation(raw: str) -> dict[str, str]:
    parts = [part.strip() for part in raw.split("|", 2)]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError("Validation must use 'name|status|detail' form.")
    return {
        "name": parts[0],
        "status": _normalize_status(parts[1]),
        "detail": parts[2] if len(parts) > 2 else "",
    }


def build_release_quality_report(
    *,
    pressure_summary_path: Path,
    report_id: str,
    validations: list[dict[str, str]] | None = None,
    ci_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pressure_summary_path = pressure_summary_path.resolve()
    pressure = summarize_pressure_run(pressure_summary_path)
    validations = validations or []
    ci_checks = [_normalize_check(row) for row in (ci_checks or [])]
    gates = {
        "pressure": _normalize_status(str(pressure["gate_status"])),
        "validations": _aggregate_status([row["status"] for row in validations]),
        "ci_checks": _aggregate_status([row["status"] for row in ci_checks]),
        "secret_safety": "pass" if pressure["secret_safety"]["no_key_or_raw_response_saved"] else "fail",
    }
    overall_status = _overall_status(gates.values())
    return {
        "schema_version": "workbench_backend_release_quality_v0.1",
        "report_id": report_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "source_artifacts": {
            "pressure_summary": str(pressure_summary_path),
            "pressure_benchmark_dir": pressure.get("benchmark_dir", ""),
        },
        "gates": gates,
        "pressure": pressure,
        "validations": validations,
        "ci_checks": ci_checks,
        "interview_metrics": _interview_metrics(pressure),
        "caveats": _caveats(pressure, validations, ci_checks),
    }


def summarize_pressure_run(summary_path: Path) -> dict[str, Any]:
    summary = _read_json(summary_path)
    results = summary.get("results") or []
    case_rows = [_summarize_case_row(row) for row in results]
    elapsed_values = [row["subprocess_elapsed_ms"] for row in case_rows]
    token_values = [row["estimated_total_tokens"] for row in case_rows]
    llm_latency_values = [row["llm_phase_latency_sum_ms"] for row in case_rows]
    evidence_latency_values = [
        row["evidence_context_elapsed_ms_max"] for row in case_rows if row["evidence_context_elapsed_ms_max"] is not None
    ]
    serial_elapsed_ms = sum(elapsed_values)
    wall_elapsed_ms = _to_int(summary.get("elapsed_ms"))
    users = _to_int(summary.get("users"))
    case_run_count = _to_int(summary.get("case_run_count")) or len(case_rows)
    return {
        "benchmark_id": summary.get("benchmark_id", ""),
        "benchmark_dir": summary.get("benchmark_dir", ""),
        "gate_status": summary.get("gate_status", ""),
        "users": users,
        "iterations": _to_int(summary.get("iterations")),
        "case_ids": summary.get("case_ids") or [],
        "case_run_count": case_run_count,
        "pass_count": _to_int(summary.get("pass_count")),
        "fail_count": _to_int(summary.get("fail_count")),
        "timeout_count": _to_int(summary.get("timeout_count")),
        "exit_fail_count": _to_int(summary.get("exit_fail_count")),
        "pass_rate": _ratio(_to_int(summary.get("pass_count")), case_run_count),
        "wall_elapsed_ms": wall_elapsed_ms,
        "duration_ms": {
            "min": min(elapsed_values) if elapsed_values else 0,
            "p50": _percentile(elapsed_values, 50),
            "p95": _percentile(elapsed_values, 95),
            "avg": _avg(elapsed_values),
            "max": max(elapsed_values) if elapsed_values else 0,
        },
        "token_usage": {
            "total": sum(token_values),
            "min": min(token_values) if token_values else 0,
            "p50": _percentile(token_values, 50),
            "p95": _percentile(token_values, 95),
            "avg": _avg(token_values),
            "max": max(token_values) if token_values else 0,
            "known_input_total": sum(row["known_input_tokens"] for row in case_rows),
            "known_output_total": sum(row["known_output_tokens"] for row in case_rows),
        },
        "latency_breakdown_ms": {
            "llm_phase_sum_avg": _avg(llm_latency_values),
            "evidence_context_max_avg": _avg(evidence_latency_values),
        },
        "throughput": {
            "successful_runs_per_hour": _per_hour(_to_int(summary.get("pass_count")), wall_elapsed_ms),
            "all_runs_per_hour": _per_hour(case_run_count, wall_elapsed_ms),
            "serial_elapsed_ms": serial_elapsed_ms,
            "concurrency_gain": round(serial_elapsed_ms / wall_elapsed_ms, 3) if wall_elapsed_ms else 0,
            "parallel_efficiency": round((serial_elapsed_ms / wall_elapsed_ms) / users, 3)
            if wall_elapsed_ms and users
            else 0,
        },
        "tool_calls": {
            "total": sum(row["tool_calls"] for row in case_rows),
            "avg_per_run": _avg([row["tool_calls"] for row in case_rows]),
        },
        "case_rows": case_rows,
        "case_groups": _group_case_rows(case_rows),
        "secret_safety": {
            "api_key_env": summary.get("api_key_env", ""),
            "api_key_saved": bool(summary.get("api_key_saved")),
            "raw_llm_response_saved": bool(summary.get("raw_llm_response_saved")),
            "no_key_or_raw_response_saved": not bool(summary.get("api_key_saved"))
            and not bool(summary.get("raw_llm_response_saved")),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    pressure = report["pressure"]
    lines = [
        f"# Workbench Backend Release Quality Report: {report['report_id']}",
        "",
        "## Executive Summary",
        "",
        f"- Overall status: `{report['overall_status']}`",
        f"- Pressure gate: `{report['gates']['pressure']}`; pass rate `{_pct(pressure['pass_rate'])}`",
        f"- CI gate: `{report['gates']['ci_checks']}`; validation gate: `{report['gates']['validations']}`",
        f"- Secret safety: `{report['gates']['secret_safety']}`",
        "",
        "## Backend Quality Gates",
        "",
        "| Gate | Status |",
        "| --- | --- |",
    ]
    for name, status in report["gates"].items():
        lines.append(f"| `{name}` | `{status}` |")
    lines.extend(
        [
            "",
            "## Pressure And Performance",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Concurrent users | {pressure['users']} |",
            f"| Case runs | {pressure['case_run_count']} |",
            f"| Passed / failed / timeout | {pressure['pass_count']} / {pressure['fail_count']} / {pressure['timeout_count']} |",
            f"| Wall time | {_fmt_seconds(pressure['wall_elapsed_ms'])} |",
            f"| Latency p50 / p95 / max | {_fmt_seconds(pressure['duration_ms']['p50'])} / {_fmt_seconds(pressure['duration_ms']['p95'])} / {_fmt_seconds(pressure['duration_ms']['max'])} |",
            f"| Successful runs/hour | {pressure['throughput']['successful_runs_per_hour']:.2f} |",
            f"| Concurrency gain | {pressure['throughput']['concurrency_gain']:.2f}x |",
            f"| Parallel efficiency | {_pct(pressure['throughput']['parallel_efficiency'])} |",
            "",
            "## Token And Cost Proxy",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Total tokens | {pressure['token_usage']['total']:,} |",
            f"| Tokens/run avg | {pressure['token_usage']['avg']:,} |",
            f"| Tokens/run p50 / p95 / max | {pressure['token_usage']['p50']:,} / {pressure['token_usage']['p95']:,} / {pressure['token_usage']['max']:,} |",
            f"| Known input tokens | {pressure['token_usage']['known_input_total']:,} |",
            f"| Known output tokens | {pressure['token_usage']['known_output_total']:,} |",
            "",
            "## Per-Case Summary",
            "",
            "| Case | Runs | Pass rate | Avg latency | Avg tokens | Avg tool calls |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in pressure["case_groups"]:
        lines.append(
            "| `{case_id}` | {runs} | {pass_rate} | {latency} | {tokens:,} | {tools:.1f} |".format(
                case_id=row["case_id"],
                runs=row["runs"],
                pass_rate=_pct(row["pass_rate"]),
                latency=_fmt_seconds(row["avg_subprocess_elapsed_ms"]),
                tokens=row["avg_estimated_total_tokens"],
                tools=row["avg_tool_calls"],
            )
        )
    lines.extend(
        [
            "",
            "## Local Validations",
            "",
            "| Validation | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    if report["validations"]:
        for row in report["validations"]:
            lines.append(f"| `{row['name']}` | `{row['status']}` | {row.get('detail', '')} |")
    else:
        lines.append("| _none supplied_ | `not_evaluated` |  |")
    lines.extend(
        [
            "",
            "## CI Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    if report["ci_checks"]:
        for row in report["ci_checks"]:
            detail = row.get("detail") or row.get("link") or ""
            lines.append(f"| `{row['name']}` | `{row['status']}` | {detail} |")
    else:
        lines.append("| _none supplied_ | `not_evaluated` |  |")
    lines.extend(
        [
            "",
            "## Interview Narrative",
            "",
            "- Correctness: report API, job lifecycle, deployment smoke, and selected real LLM case pass rates separately.",
            "- Performance: report p50/p95/max latency, timeout rate, throughput, and concurrency gain instead of only average latency.",
            "- Cost: report total tokens, tokens per run, and component-level token coverage caveats.",
            "- Reliability: report trace/log/artifact completeness through Workbench validations and pressure child summaries.",
            "",
            "## Caveats",
            "",
        ]
    )
    for caveat in report["caveats"]:
        lines.append(f"- {caveat}")
    lines.append("")
    return "\n".join(lines)


def _summarize_case_row(row: dict[str, Any]) -> dict[str, Any]:
    child_summary = _read_json(Path(str(row.get("summary_path") or "")))
    case = (child_summary.get("cases") or [{}])[0]
    audit = case.get("agent_audit") or {}
    components = _extract_llm_components(audit)
    evidence_elapsed = _extract_evidence_elapsed_ms(audit)
    total_tokens = sum(_to_int(item.get("total_tokens")) for item in components)
    return {
        "user_id": _to_int(row.get("user_id")),
        "iteration": _to_int(row.get("iteration")),
        "ordinal": _to_int(row.get("ordinal")),
        "case_id": row.get("case_id", ""),
        "run_id": row.get("run_id", ""),
        "passed": _row_passed(row),
        "subprocess_elapsed_ms": _to_int(row.get("elapsed_ms")),
        "child_eval_elapsed_ms": _to_int(child_summary.get("elapsed_ms")),
        "llm_phase_latency_sum_ms": sum(_to_int(item.get("latency_ms")) for item in components),
        "evidence_context_elapsed_ms_max": max(evidence_elapsed) if evidence_elapsed else None,
        "tool_calls": _to_int(row.get("child_total_tool_calls")),
        "estimated_total_tokens": total_tokens,
        "known_input_tokens": sum(_to_int(item.get("input_tokens")) for item in components),
        "known_output_tokens": sum(_to_int(item.get("output_tokens")) for item in components),
        "components": components,
    }


def _extract_llm_components(audit: dict[str, Any]) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    _add_diag_component(components, "research_lead", (audit.get("research_lead") or {}).get("diagnostics") or {})
    specialists = (audit.get("specialists") or {}).get("route_results") or []
    for index, specialist in enumerate(specialists, start=1):
        components.append(
            {
                "component": f"specialist_{index}",
                "latency_ms": _to_int(specialist.get("latency_ms")),
                "total_tokens": _to_int(specialist.get("total_tokens")),
                "input_tokens": _to_int(specialist.get("input_tokens")),
                "output_tokens": _to_int(specialist.get("output_tokens")),
            }
        )
    _add_diag_component(components, "memo_writer", (audit.get("memo_writer") or {}).get("diagnostics") or {})
    _add_diag_component(components, "verifier", (audit.get("verifier") or {}).get("diagnostics") or {})
    return [item for item in components if item["latency_ms"] or item["total_tokens"]]


def _add_diag_component(components: list[dict[str, Any]], name: str, diag: dict[str, Any]) -> None:
    components.append(
        {
            "component": name,
            "latency_ms": _to_int(diag.get("latency_ms")),
            "total_tokens": _to_int(diag.get("total_tokens")),
            "input_tokens": _to_int(diag.get("input_tokens")),
            "output_tokens": _to_int(diag.get("output_tokens")),
        }
    )


def _extract_evidence_elapsed_ms(audit: dict[str, Any]) -> list[int]:
    out: list[int] = []
    tool_calls = (audit.get("evidence_operators") or {}).get("tool_calls") or []
    for tool_call in tool_calls:
        runtime = ((tool_call.get("runtime_summary") or {}).get("context_runtime") or {})
        elapsed = _to_int(runtime.get("elapsed_ms"))
        if elapsed:
            out.append(elapsed)
    return out


def _group_case_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row["case_id"]), []).append(row)
    out: list[dict[str, Any]] = []
    for case_id, case_rows in sorted(groups.items()):
        runs = len(case_rows)
        out.append(
            {
                "case_id": case_id,
                "runs": runs,
                "pass_rate": _ratio(sum(1 for row in case_rows if row["passed"]), runs),
                "avg_subprocess_elapsed_ms": _avg([row["subprocess_elapsed_ms"] for row in case_rows]),
                "avg_estimated_total_tokens": _avg([row["estimated_total_tokens"] for row in case_rows]),
                "avg_tool_calls": _avg_float([row["tool_calls"] for row in case_rows]),
            }
        )
    return out


def _interview_metrics(pressure: dict[str, Any]) -> dict[str, Any]:
    return {
        "correctness": {
            "pressure_pass_rate": pressure["pass_rate"],
            "timeouts": pressure["timeout_count"],
            "exit_failures": pressure["exit_fail_count"],
        },
        "performance": {
            "latency_p50_ms": pressure["duration_ms"]["p50"],
            "latency_p95_ms": pressure["duration_ms"]["p95"],
            "throughput_successful_runs_per_hour": pressure["throughput"]["successful_runs_per_hour"],
            "concurrency_gain": pressure["throughput"]["concurrency_gain"],
        },
        "cost_proxy": {
            "total_tokens": pressure["token_usage"]["total"],
            "avg_tokens_per_run": pressure["token_usage"]["avg"],
            "known_input_tokens": pressure["token_usage"]["known_input_total"],
            "known_output_tokens": pressure["token_usage"]["known_output_total"],
        },
        "reliability": {
            "secret_safety": pressure["secret_safety"]["no_key_or_raw_response_saved"],
            "tool_calls_total": pressure["tool_calls"]["total"],
        },
    }


def _caveats(
    pressure: dict[str, Any], validations: list[dict[str, str]], ci_checks: list[dict[str, Any]]
) -> list[str]:
    caveats = [
        "This is a bounded pressure smoke, not a full 17-case soak test.",
        "Token totals are component-level estimates from child summaries; not all components expose input/output splits.",
    ]
    if not validations:
        caveats.append("No local validation records were supplied to the report generator.")
    if not ci_checks:
        caveats.append("No CI check records were supplied to the report generator.")
    if pressure["case_run_count"] < 10:
        caveats.append("The sample size is too small for a stable p95 latency claim.")
    return caveats


def _load_checks(args: argparse.Namespace) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if args.checks_json:
        payload = json.loads(args.checks_json.read_text(encoding="utf-8"))
        checks.extend(payload if isinstance(payload, list) else payload.get("checks", []))
    if args.fetch_pr_checks:
        command = [
            "gh",
            "pr",
            "checks",
            str(args.pr_number),
            "--repo",
            args.repo,
            "--json",
            "name,state,link,startedAt,completedAt,bucket",
        ]
        result = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        if result.returncode == 0:
            checks.extend(json.loads(result.stdout))
        else:
            checks.append(
                {
                    "name": "github_checks_fetch",
                    "status": "unknown",
                    "detail": (result.stderr or result.stdout).strip()[:300],
                }
            )
    return checks


def _normalize_check(row: dict[str, Any]) -> dict[str, Any]:
    state = row.get("status") or row.get("state") or row.get("bucket") or ""
    out = {
        "name": str(row.get("name") or "unknown_check"),
        "status": _normalize_status(str(state)),
        "detail": str(row.get("detail") or ""),
    }
    if row.get("link"):
        out["link"] = row["link"]
    if row.get("startedAt"):
        out["started_at"] = row["startedAt"]
    if row.get("completedAt"):
        out["completed_at"] = row["completedAt"]
    return out


def _normalize_status(value: str) -> str:
    lowered = value.strip().lower().replace("-", "_")
    if lowered in PASS_STATES:
        return "pass"
    if lowered in FAIL_STATES:
        return "fail"
    if lowered in {"pending", "queued", "in_progress", "waiting"}:
        return "pending"
    if lowered in {"", "none", "null", "unknown", "skipped"}:
        return "not_evaluated"
    return lowered


def _aggregate_status(statuses: list[str]) -> str:
    if not statuses:
        return "not_evaluated"
    normalized = [_normalize_status(status) for status in statuses]
    if any(status == "fail" for status in normalized):
        return "fail"
    if any(status == "pending" for status in normalized):
        return "pending"
    if all(status == "pass" for status in normalized):
        return "pass"
    return "review"


def _overall_status(statuses: Any) -> str:
    normalized = [_normalize_status(str(status)) for status in statuses]
    if any(status == "fail" for status in normalized):
        return "fail"
    if any(status == "pending" for status in normalized):
        return "pending"
    if any(status in {"not_evaluated", "review"} for status in normalized):
        return "review"
    return "pass"


def _row_passed(row: dict[str, Any]) -> bool:
    return (
        not bool(row.get("timed_out"))
        and _to_int(row.get("exit_code")) == 0
        and _normalize_status(str(row.get("child_gate_status") or "")) == "pass"
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _to_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _avg(values: list[int]) -> int:
    return int(sum(values) / len(values)) if values else 0


def _avg_float(values: list[int]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _per_hour(count: int, elapsed_ms: int) -> float:
    if not elapsed_ms:
        return 0.0
    return round(count / (elapsed_ms / 3_600_000), 3)


def _percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, math.ceil((percentile / 100) * len(ordered)) - 1)
    return ordered[index]


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_seconds(ms: int) -> str:
    return f"{ms / 1000:.1f}s"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
