from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.runtime_bridge.eval_store import read_eval_counts, record_eval_case_result, record_eval_gold_promotion


def main() -> None:
    args = parse_args()
    report = run_gate(args)
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    workbench_summary = _read_json(args.workbench_summary)
    source_summary_path = Path(str(workbench_summary.get("source_summary_path") or ""))
    if not source_summary_path.is_absolute():
        source_summary_path = REPO_ROOT / source_summary_path
    source_summary = _read_json(source_summary_path)
    output_dir = Path(str(workbench_summary.get("output_dir") or source_summary.get("output_dir") or source_summary_path.parent))
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    quality_audit = _read_json(output_dir / "multi_agent_output_quality_audit.json")
    quality_by_case = {
        str(row.get("case_id")): row
        for row in quality_audit.get("cases") or []
        if isinstance(row, Mapping) and row.get("case_id")
    }
    eval_id = str(args.eval_id or "agent_graph_vnext_diagnostic_probe")
    run_id = str(workbench_summary.get("run_id") or source_summary.get("run_id") or args.workbench_summary.stem)
    case_reports: list[dict[str, Any]] = []
    for case in source_summary.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        case_id = str(case.get("case_id") or "").strip()
        if not case_id:
            continue
        quality = quality_by_case.get(case_id, {})
        status = "pass" if case.get("gate_status") == "pass" else "fail"
        failure_events = _case_failure_events(case, quality=quality, output_dir=output_dir)
        record = record_eval_case_result(
            args.eval_store,
            {
                "eval_id": eval_id,
                "case_id": case_id,
                "run_id": run_id,
                "status": status,
                "score": 1.0 if status == "pass" else 0.0,
                "criteria_version": "r12_online_eval_runtime_loop_v0_1",
                "node_results": _case_node_results(case, quality=quality),
                "failure_events": failure_events,
                "artifact_refs": _case_artifact_refs(output_dir, case_id),
            },
        )
        promotion_record = {"status": "skip", "reason": "case_not_pass"}
        if status == "pass" and not _gold_candidate_exists(args.eval_store, eval_id=eval_id, case_id=case_id, run_id=run_id):
            promotion_record = record_eval_gold_promotion(
                args.eval_store,
                {
                    "eval_id": eval_id,
                    "case_id": case_id,
                    "state": "candidate",
                    "criteria_version": "r12_online_eval_runtime_loop_v0_1",
                    "review_method": "automatic_candidate_from_r12_pass_requires_human_review",
                    "run_id": run_id,
                    "gate_status": case.get("gate_status"),
                    "artifact_refs": _case_artifact_refs(output_dir, case_id),
                },
            )
        case_reports.append(
            {
                "case_id": case_id,
                "status": status,
                "gate_status": case.get("gate_status"),
                "quality_flags": _quality_flags(quality),
                "failure_event_count": len(failure_events),
                "eval_record_status": record.get("status"),
                "gold_promotion_status": promotion_record.get("status"),
            }
        )
    counts = read_eval_counts(args.eval_store)
    errors = []
    expected_cases = len(case_reports)
    if expected_cases == 0:
        errors.append({"type": "no_cases_found"})
    if not all(case["status"] == "pass" for case in case_reports):
        errors.append({"type": "case_gate_not_all_pass", "cases": case_reports})
    if counts.get("eval_case_result", 0) < expected_cases:
        errors.append({"type": "eval_case_result_missing", "counts": counts})
    if counts.get("eval_metric_result", 0) <= 0:
        errors.append({"type": "eval_metric_trend_missing", "counts": counts})
    if counts.get("eval_dashboard_snapshot", 0) <= 0:
        errors.append({"type": "eval_dashboard_snapshot_missing", "counts": counts})
    if counts.get("eval_gold_promotion", 0) < expected_cases:
        errors.append({"type": "eval_gold_candidate_missing", "counts": counts})
    if counts.get("eval_failure_event", 0) <= 0:
        errors.append({"type": "eval_failure_or_quality_queue_missing", "counts": counts})
    return {
        "schema_version": "finsight_r12_eval_runtime_loop_gate_v0_1",
        "status": "fail" if errors else "pass",
        "eval_id": eval_id,
        "run_id": run_id,
        "workbench_summary": str(args.workbench_summary.resolve()),
        "source_summary_path": str(source_summary_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "eval_store": str(args.eval_store.resolve()),
        "counts": counts,
        "case_reports": case_reports,
        "checks": {
            "case_results_recorded": counts.get("eval_case_result", 0) >= expected_cases,
            "latency_cost_metrics_recorded": counts.get("eval_metric_result", 0) > 0,
            "dashboard_snapshot_recorded": counts.get("eval_dashboard_snapshot", 0) > 0,
            "gold_candidates_recorded": counts.get("eval_gold_promotion", 0) >= expected_cases,
            "failure_or_quality_queue_recorded": counts.get("eval_failure_event", 0) > 0,
        },
        "errors": errors,
    }


def _case_node_results(case: Mapping[str, Any], *, quality: Mapping[str, Any]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for name in (
        "elapsed_ms",
        "tool_call_count",
        "budgeted_tool_call_count",
        "cached_tool_call_count",
        "rendered_answer_chars",
        "memo_claim_count",
        "memo_dimension_analysis_count",
    ):
        value = _number(case.get(name))
        if value is not None:
            metrics.append({"name": name, "value": value})
    token_stats = quality.get("token_stats") if isinstance(quality.get("token_stats"), Mapping) else {}
    for name in ("total_tokens", "memo_writer_tokens", "verifier_tokens", "specialist_tokens"):
        value = _number(token_stats.get(name))
        if value is not None:
            metrics.append({"name": name, "value": value})
    cost_quality = quality.get("cost_quality_stats") if isinstance(quality.get("cost_quality_stats"), Mapping) else {}
    for name in ("tokens_per_supported_claim_card", "tokens_per_rendered_memo_claim", "memo_chars_per_total_token"):
        value = _number(cost_quality.get(name))
        if value is not None:
            metrics.append({"name": name, "value": value})
    return [
        {
            "node": f"case:{case.get('case_id') or 'unknown'}",
            "status": "pass" if case.get("gate_status") == "pass" else "fail",
            "metric_count": len(metrics),
            "metrics": metrics,
        },
        {
            "node": "online_eval_quality_queue",
            "status": "pass",
            "metric_count": 1,
            "metrics": [{"name": "quality_flag_count", "value": len(_quality_flags(quality))}],
        },
    ]


def _case_failure_events(case: Mapping[str, Any], *, quality: Mapping[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    case_id = str(case.get("case_id") or "")
    if case.get("gate_status") != "pass":
        events.append(
            {
                "failure_type": "r12_case_gate_failed",
                "node": "r12_release_gate",
                "expected": "gate_status pass",
                "actual": str(case.get("gate_status")),
                "artifact_refs": _case_artifact_refs(output_dir, case_id),
                "status": "blocking",
            }
        )
    for flag in _quality_flags(quality):
        events.append(
            {
                "failure_type": f"quality_risk:{flag}",
                "node": "online_eval_quality_queue",
                "expected": "risk tracked for later budget/quality tuning",
                "actual": str(flag),
                "artifact_refs": _case_artifact_refs(output_dir, case_id),
                "status": "observed_quality_risk",
            }
        )
    return events


def _quality_flags(quality: Mapping[str, Any]) -> list[str]:
    flags = quality.get("quality_flags")
    if flags is None:
        flags = quality.get("flags")
    return [str(flag) for flag in flags or [] if str(flag).strip()]


def _case_artifact_refs(output_dir: Path, case_id: str) -> list[dict[str, str]]:
    case_dir = output_dir / case_id
    refs = [
        ("case_score", case_dir / "real_chain_case_score.json"),
        ("memo_answer", case_dir / "memo_answer.json"),
        ("claim_cards", case_dir / "claim_cards.json"),
        ("typed_gap_ledger", case_dir / "typed_gap_ledger.json"),
        ("gate_registry", case_dir / "gate_registry_eval_matrix.json"),
        ("run_audit", case_dir / "run_audit_materialization_report.json"),
        ("rendered_answer", case_dir / "qwen" / "rendered_answer.md"),
    ]
    return [{"kind": kind, "uri": str(path.resolve())} for kind, path in refs if path.exists()]


def _gold_candidate_exists(db_path: Path, *, eval_id: str, case_id: str, run_id: str) -> bool:
    if not db_path.exists():
        return False
    with sqlite3.connect(db_path) as conn:
        try:
            rows = conn.execute(
                "select payload_json from eval_gold_promotion where eval_id = ? and case_id = ? and state = 'candidate'",
                (eval_id, case_id),
            ).fetchall()
        except sqlite3.Error:
            return False
    return any(run_id in str(row[0]) for row in rows)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize and gate the R12 eval runtime loop from a real Workbench eval summary.")
    parser.add_argument(
        "--workbench-summary",
        type=Path,
        default=REPO_ROOT / "reports" / "quality" / "workbench_eval" / "r12_activation_diagnostic_probe_milvus_bound_20260614_r2_agent_graph_vnext_diagnostic_probe.json",
    )
    parser.add_argument(
        "--eval-store",
        type=Path,
        default=REPO_ROOT / "data" / "workbench_private" / "runtime_bridge" / "eval_store.sqlite",
    )
    parser.add_argument("--eval-id", default="agent_graph_vnext_diagnostic_probe")
    parser.add_argument(
        "--output-path",
        type=Path,
        default=REPO_ROOT / "reports" / "quality" / "r12_eval_runtime_loop_gate" / "r12_eval_runtime_loop_gate_report.json",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
