from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
SCRIPT_ROOT = REPO_ROOT / "scripts"
for root in (SRC_ROOT, SCRIPT_DIR, SCRIPT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import eval_multi_agent_evidence_operator_gate as s3  # noqa: E402
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph  # noqa: E402


DEFAULT_EVIDENCE_SUMMARY = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "multi_agent_evidence_operator_diagnostic"
    / "20260601_fin_agent_s3_after_s2_relationship_inference_v0_1"
    / "evidence_operator_diagnostic.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_coverage_reflection_diagnostic"
SUMMARY_SCHEMA_VERSION = "sec_agent_coverage_reflection_diagnostic_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S4 Coverage / Reflection gate from passed S1/S2/S3 artifacts.")
    parser.add_argument("--activation-summary", type=Path, default=s3.DEFAULT_ACTIVATION_SUMMARY)
    parser.add_argument("--relationship-summary", type=Path, default=s3.DEFAULT_RELATIONSHIP_SUMMARY)
    parser.add_argument("--evidence-summary", type=Path, default=Path(os.environ.get("EVIDENCE_OPERATOR_SUMMARY", str(DEFAULT_EVIDENCE_SUMMARY))))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--skip-second-pass", action="store_true", help="Audit reflection only; do not execute optional second-pass even if allowed.")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    activation_summary = _read_json(args.activation_summary)
    relationship_summary = _read_json(args.relationship_summary) if args.relationship_summary.exists() else {}
    evidence_summary = _read_json(args.evidence_summary)
    relationship_artifact_root = s3._summary_artifact_root(relationship_summary, args.relationship_summary)
    evidence_artifact_root = s3._summary_artifact_root(evidence_summary, args.evidence_summary)
    cases = _selected_cases(_coverage_cases(activation_summary, evidence_summary), args.case_id)
    run_id = args.run_id or _default_run_id()
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage_graph = build_multi_agent_orchestration_graph(
        use_checkpointer=False,
        entry_node="coverage_reflection",
        stop_after_node="coverage_reflection",
    )
    second_pass_graph = build_multi_agent_orchestration_graph(
        use_checkpointer=False,
        entry_node="optional_second_pass",
        stop_after_node="optional_second_pass",
    )
    started = time.time()
    scores: list[dict[str, Any]] = []

    for ordinal, case in enumerate(cases, start=1):
        case_started = time.time()
        case_id = str(case.get("case_id") or f"case_{ordinal}")
        case_dir = output_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        relationship_artifacts = s3._relationship_artifacts(case_id, relationship_artifact_root)
        state = s3._initial_state(case, relationship_artifacts, case_dir, run_id=run_id, args=_s3_args_from_summary(evidence_summary))
        state = _inject_s3_artifacts(state, evidence_artifact_root, case_id)
        coverage_result = coverage_graph.invoke(state, config={"configurable": {"thread_id": f"{run_id}-{case_id}-s4-coverage"}})
        final_result = coverage_result
        decision = coverage_result.get("multi_agent_second_pass_decision") if isinstance(coverage_result.get("multi_agent_second_pass_decision"), Mapping) else {}
        if decision.get("allowed") and not args.skip_second_pass:
            final_result = second_pass_graph.invoke(
                coverage_result,
                config={"configurable": {"thread_id": f"{run_id}-{case_id}-s4-second-pass"}},
            )
        score = _score_case(
            case,
            coverage_result,
            final_result,
            elapsed_sec=round(time.time() - case_started, 4),
            ordinal=ordinal,
            total=len(cases),
            s3_row_counts=_s3_row_counts(evidence_artifact_root, case_id),
        )
        (case_dir / "coverage_reflection_case_score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "coverage_reflection_result_summary.json").write_text(
            json.dumps(_result_summary(coverage_result, final_result), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        scores.append(score)

    summary = _aggregate(
        run_id=run_id,
        args=args,
        activation_summary=activation_summary,
        relationship_summary=relationship_summary,
        evidence_summary=evidence_summary,
        scores=scores,
        elapsed_sec=round(time.time() - started, 4),
        output_dir=output_dir,
    )
    summary_path = output_dir / "coverage_reflection_diagnostic.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_stdout_summary(summary, summary_path), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _coverage_cases(activation_summary: Mapping[str, Any], evidence_summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence_case_ids = {
        str(case.get("case_id") or "")
        for case in evidence_summary.get("cases") or []
        if isinstance(case, Mapping) and str(case.get("status") or "") == "pass"
    }
    cases = []
    for case in activation_summary.get("cases") or []:
        if not isinstance(case, Mapping) or str(case.get("status") or "") != "pass":
            continue
        case_id = str(case.get("case_id") or "")
        if case_id in evidence_case_ids:
            cases.append(dict(case))
    return cases


def _selected_cases(cases: list[dict[str, Any]], selected_ids: list[str]) -> list[dict[str, Any]]:
    if not selected_ids:
        return cases
    selected = {str(item) for item in selected_ids}
    return [case for case in cases if str(case.get("case_id") or "") in selected]


def _s3_args_from_summary(evidence_summary: Mapping[str, Any]) -> argparse.Namespace:
    config = evidence_summary.get("retrieval_runtime_config") if isinstance(evidence_summary.get("retrieval_runtime_config"), Mapping) else {}
    return argparse.Namespace(
        manifest_path=_path_or_default(config.get("manifest_path_ref"), s3.DEFAULT_SECTOR_DEPTH_MANIFEST),
        bm25_index_dir=_path_or_default(config.get("bm25_index_ref"), s3.DEFAULT_SECTOR_DEPTH_BM25),
        object_bm25_index_dir=_path_or_default(config.get("object_bm25_index_ref"), s3.DEFAULT_SECTOR_DEPTH_OBJECT_BM25),
        ledger_store_path=_path_or_default(config.get("ledger_store_ref"), s3.DEFAULT_LEDGER_STORE),
        market_evidence_path=_path_or_default(config.get("market_evidence_ref"), s3.DEFAULT_MARKET_EVIDENCE),
        market_catalog_path=_optional_path(config.get("market_catalog_ref")),
        industry_evidence_path=_path_or_default(config.get("industry_evidence_ref"), s3.DEFAULT_INDUSTRY_EVIDENCE),
        industry_snapshot_db_path=_optional_path(config.get("industry_snapshot_db_ref")),
        sector_depth_pack_path=_path_or_default(config.get("sector_depth_pack_ref"), s3.DEFAULT_SECTOR_DEPTH_PACK),
        milvus_db_path=_optional_path(config.get("milvus_db_ref")),
        milvus_collection_name=str(config.get("milvus_collection_name") or ""),
        milvus_vector_kinds=",".join(str(item) for item in config.get("milvus_vector_kinds") or []),
        milvus_top_k=int(config.get("milvus_top_k") or 40),
        embedding_model=str(config.get("embedding_model") or ""),
        market_snapshot_id=str(config.get("market_snapshot_id") or s3.DEFAULT_MARKET_SNAPSHOT_ID),
        market_as_of_date=str(config.get("market_as_of_date") or s3.DEFAULT_MARKET_AS_OF_DATE),
        bge_model=_path_or_default(config.get("bge_model_ref"), s3.DEFAULT_BGE_MODEL),
        bge_device=str(config.get("bge_device") or "auto"),
        context_runner=str(config.get("context_runner") or "in_process"),
        evidence_top_k=0,
        object_top_k=0,
        reranker_candidate_limit=int(config.get("reranker_candidate_limit") or 0),
        reranker_top_k=int(config.get("reranker_top_k") or 0),
        reranker_batch_size=8,
        reranker_max_length=512,
        reranker_doc_max_chars=0,
    )


def _path_or_default(value: Any, default: Path) -> Path:
    text = str(value or "").strip()
    if not text or text.startswith(".../") or text.startswith("...\\"):
        return default
    return Path(text)


def _optional_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text or text.startswith(".../") or text.startswith("...\\"):
        return None
    return Path(text)


def _inject_s3_artifacts(state: dict[str, Any], evidence_artifact_root: Path, case_id: str) -> dict[str, Any]:
    result = _read_json(evidence_artifact_root / case_id / "evidence_operator_result_summary.json")
    return {
        **state,
        "status": "running",
        "native_stop_after_node": "",
        "tool_observations": [dict(row) for row in result.get("tool_observations") or [] if isinstance(row, Mapping)],
        "tool_call_ledger": dict(result.get("tool_call_ledger") or state.get("tool_call_ledger") or {}),
        "source_gaps": [dict(row) for row in result.get("source_gaps") or [] if isinstance(row, Mapping)],
        "context_rows": [dict(row) for row in (result.get("context_rows") or result.get("context_row_sample") or []) if isinstance(row, Mapping)],
        "runtime_ledger_rows": [dict(row) for row in (result.get("runtime_ledger_rows") or result.get("runtime_ledger_row_sample") or []) if isinstance(row, Mapping)],
        "market_snapshot_rows": [dict(row) for row in (result.get("market_rows") or result.get("market_row_sample") or []) if isinstance(row, Mapping)],
        "industry_snapshot_rows": [dict(row) for row in (result.get("industry_rows") or result.get("industry_row_sample") or []) if isinstance(row, Mapping)],
    }


def _score_case(
    case: Mapping[str, Any],
    coverage_result: Mapping[str, Any],
    final_result: Mapping[str, Any],
    *,
    elapsed_sec: float,
    ordinal: int,
    total: int,
    s3_row_counts: Mapping[str, int],
) -> dict[str, Any]:
    report = coverage_result.get("multi_agent_reflection_report") if isinstance(coverage_result.get("multi_agent_reflection_report"), Mapping) else {}
    decision = coverage_result.get("multi_agent_second_pass_decision") if isinstance(coverage_result.get("multi_agent_second_pass_decision"), Mapping) else {}
    second_pass = final_result.get("second_pass_result") if isinstance(final_result.get("second_pass_result"), Mapping) else {}
    missing = [dict(item) for item in report.get("missing_requirements") or [] if isinstance(item, Mapping)]
    requests = [dict(item) for item in report.get("second_pass_requests") or [] if isinstance(item, Mapping)]
    source_available = bool(report.get("source_available"))
    second_pass_allowed = bool(decision.get("allowed"))
    second_pass_ran = "second_pass_result" in final_result
    added_rows = int(second_pass.get("added_row_count") or 0)
    loop_break_reason = str(final_result.get("loop_break_reason") or second_pass.get("loop_break_reason") or "")
    bounded_reason = bool(
        str(decision.get("reason") or "")
        or bool(decision.get("bounded_answer_allowed"))
        or bool(report.get("bounded_answer_allowed"))
        or bool(final_result.get("bounded_answer_allowed"))
        or loop_break_reason
    )
    checks = {
        "graph_stopped_after_coverage_reflection": coverage_result.get("status") == "stopped_after_node"
        and coverage_result.get("native_stop_after_node") == "coverage_reflection",
        "coverage_report_present": str(report.get("schema_version") or "") == "sec_agent_multi_agent_reflection_report_v0.1",
        "searchable_gaps_classified": (not missing) or all("source_available" in item for item in missing),
        "second_pass_decision_present": bool(decision),
        "source_gap_boundary_valid": _source_gap_boundary_valid(missing, source_available, decision),
        "second_pass_gain_or_bounded_reason": (
            (not second_pass_allowed and bounded_reason)
            or (second_pass_allowed and second_pass_ran and (added_rows > 0 or bounded_reason))
        ),
        "no_duplicate_or_budget_loop_break": loop_break_reason not in {"duplicate_tool_call_blocked", "tool_budget_exhausted", "agent_tool_budget_exhausted"},
        "s3_rows_available_for_reflection": sum(int(value or 0) for value in s3_row_counts.values()) > 0,
    }
    status = "pass" if all(checks.values()) else "fail"
    return {
        "case_id": case.get("case_id"),
        "ordinal": ordinal,
        "total": total,
        "prompt": case.get("prompt"),
        "status": status,
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "execution_mode": (case.get("activation_plan") or {}).get("execution_mode") if isinstance(case.get("activation_plan"), Mapping) else "",
        "reflection": {
            "sufficiency_level": report.get("sufficiency_level") or "",
            "missing_requirement_count": len(missing),
            "second_pass_request_count": len(requests),
            "source_available": source_available,
            "bounded_answer_allowed": bool(report.get("bounded_answer_allowed")),
            "trigger": report.get("trigger") or "",
        },
        "second_pass": {
            "allowed": second_pass_allowed,
            "decision_reason": decision.get("reason") or "",
            "ran": second_pass_ran,
            "added_row_count": added_rows,
            "loop_break_reason": loop_break_reason,
            "bounded_answer_allowed": bool(second_pass.get("bounded_answer_allowed") or final_result.get("bounded_answer_allowed")),
        },
        "row_counts": dict(s3_row_counts),
        "missing_requirements": [_sanitize_missing(item) for item in missing[:12]],
        "second_pass_requests": [_sanitize_missing(item) for item in requests[:12]],
    }


def _source_gap_boundary_valid(missing: list[Mapping[str, Any]], source_available: bool, decision: Mapping[str, Any]) -> bool:
    if not missing:
        return True
    unavailable = [item for item in missing if not bool(item.get("source_available"))]
    if unavailable:
        return not source_available and not bool(decision.get("allowed"))
    if source_available and any(item.get("source_available") for item in missing):
        return bool(decision.get("allowed") or str(decision.get("reason") or ""))
    return True


def _s3_row_counts(evidence_artifact_root: Path, case_id: str) -> dict[str, int]:
    result = _read_json(evidence_artifact_root / case_id / "evidence_operator_result_summary.json")
    counts = result.get("row_counts") if isinstance(result.get("row_counts"), Mapping) else {}
    return {
        "context_rows": int(counts.get("context_rows") or 0),
        "runtime_ledger_rows": int(counts.get("runtime_ledger_rows") or 0),
        "market_snapshot_rows": int(counts.get("market_snapshot_rows") or 0),
        "industry_snapshot_rows": int(counts.get("industry_snapshot_rows") or 0),
    }


def _result_summary(coverage_result: Mapping[str, Any], final_result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "coverage_status": coverage_result.get("status") or "",
        "coverage_stop_node": coverage_result.get("native_stop_after_node") or "",
        "node_trace": [dict(item) for item in final_result.get("node_trace") or [] if isinstance(item, Mapping)],
        "multi_agent_reflection_report": dict(coverage_result.get("multi_agent_reflection_report") or {}),
        "multi_agent_second_pass_decision": dict(coverage_result.get("multi_agent_second_pass_decision") or {}),
        "second_pass_result": dict(final_result.get("second_pass_result") or {}),
        "tool_call_ledger": dict(final_result.get("tool_call_ledger") or {}),
        "row_counts": {
            "context_rows": len(final_result.get("context_rows") or []),
            "runtime_ledger_rows": len(final_result.get("runtime_ledger_rows") or []),
            "market_snapshot_rows": len(final_result.get("market_snapshot_rows") or []),
            "industry_snapshot_rows": len(final_result.get("industry_snapshot_rows") or []),
        },
    }


def _aggregate(
    *,
    run_id: str,
    args: argparse.Namespace,
    activation_summary: Mapping[str, Any],
    relationship_summary: Mapping[str, Any],
    evidence_summary: Mapping[str, Any],
    scores: list[Mapping[str, Any]],
    elapsed_sec: float,
    output_dir: Path,
) -> dict[str, Any]:
    total = len(scores)
    pass_count = sum(1 for score in scores if score.get("status") == "pass")
    check_counts: dict[str, int] = {}
    for score in scores:
        for name, value in dict(score.get("checks") or {}).items():
            if value:
                check_counts[name] = check_counts.get(name, 0) + 1
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": elapsed_sec,
        "gate_status": "pass" if total > 0 and pass_count == total else "fail",
        "diagnostic_only": True,
        "activation_summary": str(args.activation_summary.resolve()),
        "activation_run_id": str(activation_summary.get("run_id") or ""),
        "relationship_summary": str(args.relationship_summary.resolve()) if args.relationship_summary.exists() else "",
        "relationship_run_id": str(relationship_summary.get("run_id") or ""),
        "evidence_summary": str(args.evidence_summary.resolve()),
        "evidence_run_id": str(evidence_summary.get("run_id") or ""),
        "output_dir": str(output_dir.resolve()),
        "metrics": {
            "case_count": total,
            "pass_count": pass_count,
            "failed_count": total - pass_count,
            "check_counts": check_counts,
            "second_pass_allowed_count": sum(1 for score in scores if (score.get("second_pass") or {}).get("allowed")),
            "second_pass_ran_count": sum(1 for score in scores if (score.get("second_pass") or {}).get("ran")),
            "second_pass_added_row_count": sum(int((score.get("second_pass") or {}).get("added_row_count") or 0) for score in scores),
            "missing_requirement_count": sum(int((score.get("reflection") or {}).get("missing_requirement_count") or 0) for score in scores),
        },
        "cases": [dict(score) for score in scores],
    }


def _sanitize_missing(row: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "requirement_id",
        "task_id",
        "question_zh",
        "priority",
        "analysis_intent",
        "tickers",
        "years",
        "filing_types",
        "source_tiers",
        "source_families",
        "source_family_gaps",
        "metric_families",
        "evidence_routes",
        "operator_owners",
        "source_available",
        "reason",
    )
    return {key: row.get(key) for key in allowed if key in row}


def _stdout_summary(summary: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "run_id": summary.get("run_id"),
        "gate_status": summary.get("gate_status"),
        "output_path": str(output_path.resolve()),
        "metrics": summary.get("metrics"),
        "failed_cases": [
            {
                "case_id": case.get("case_id"),
                "failed_checks": [name for name, value in dict(case.get("checks") or {}).items() if not value],
            }
            for case in summary.get("cases") or []
            if isinstance(case, Mapping) and case.get("status") != "pass"
        ],
    }


def _default_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_fin_agent_s4_coverage_reflection_gate_%H%M%S")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
