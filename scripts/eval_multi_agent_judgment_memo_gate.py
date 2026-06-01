from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SCRIPT_ROOT = REPO_ROOT / "scripts"
for root in (SRC_ROOT, SCRIPT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import eval_multi_agent_coverage_reflection_gate as s4  # noqa: E402
import eval_multi_agent_evidence_operator_gate as s3  # noqa: E402
import eval_multi_agent_specialist_layer_gate as s5  # noqa: E402
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph_from_env  # noqa: E402
from sec_agent.multi_agent_contracts import aggregate_specialist_judgment_plan, verify_specialist_outputs_for_memo  # noqa: E402


DEFAULT_SPECIALIST_SUMMARY = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "multi_agent_specialist_layer_diagnostic"
    / "20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1"
    / "specialist_layer_diagnostic.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_judgment_memo_diagnostic"
SUMMARY_SCHEMA_VERSION = "sec_agent_judgment_memo_diagnostic_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S6/S7/S8 Judgment/Memo/Verifier gate from passed S5 Specialist artifacts.")
    parser.add_argument("--specialist-summary", type=Path, default=Path(os.environ.get("SPECIALIST_LAYER_SUMMARY", str(DEFAULT_SPECIALIST_SUMMARY))))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("MEMO_TEMPERATURE", "0")))
    parser.add_argument("--memo-max-tokens", type=int, default=int(os.environ.get("MEMO_MAX_TOKENS", "2600")))
    parser.add_argument("--verifier-max-tokens", type=int, default=int(os.environ.get("VERIFIER_MAX_TOKENS", "1000")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("MEMO_TIMEOUT_S", "180")))
    parser.add_argument("--max-repair-attempts", type=int, default=int(os.environ.get("MEMO_MAX_REPAIR_ATTEMPTS", "1")))
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    specialist_summary = _read_json(args.specialist_summary)
    activation_summary = _read_json(Path(specialist_summary.get("activation_summary") or s3.DEFAULT_ACTIVATION_SUMMARY))
    relationship_summary = _read_json(Path(specialist_summary.get("relationship_summary") or s3.DEFAULT_RELATIONSHIP_SUMMARY))
    evidence_summary = _read_json(Path(specialist_summary.get("evidence_summary") or ""))
    coverage_summary = _read_json(Path(specialist_summary.get("coverage_summary") or ""))
    specialist_artifact_root = Path(specialist_summary.get("output_dir") or args.specialist_summary.parent)
    relationship_artifact_root = Path(relationship_summary.get("output_dir") or Path(specialist_summary.get("relationship_summary") or ".").parent)
    evidence_artifact_root = Path(evidence_summary.get("output_dir") or Path(specialist_summary.get("evidence_summary") or ".").parent)
    coverage_artifact_root = Path(coverage_summary.get("output_dir") or Path(specialist_summary.get("coverage_summary") or ".").parent)
    case_scores_by_id = {
        str(case.get("case_id") or ""): dict(case)
        for case in specialist_summary.get("cases") or []
        if isinstance(case, Mapping) and str(case.get("status") or "") == "pass"
    }
    cases = [
        case
        for case in s5._selected_cases(s5._specialist_cases(activation_summary, coverage_summary), args.case_id)
        if str(case.get("case_id") or "") in case_scores_by_id
    ]
    run_id = args.run_id or _default_run_id()
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = build_multi_agent_orchestration_graph_from_env(
        env=_graph_env(args),
        use_checkpointer=False,
        entry_node="memo_writer",
        stop_after_node="verifier",
    )

    started = time.time()
    scores: list[dict[str, Any]] = []
    for ordinal, case in enumerate(cases, start=1):
        case_started = time.time()
        case_id = str(case.get("case_id") or f"case_{ordinal}")
        case_dir = output_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        relationship_artifacts = s3._relationship_artifacts(case_id, relationship_artifact_root)
        state = s3._initial_state(case, relationship_artifacts, case_dir, run_id=run_id, args=s4._s3_args_from_summary(evidence_summary))
        state = s4._inject_s3_artifacts(state, evidence_artifact_root, case_id)
        state = s5._inject_s4_artifacts(state, coverage_artifact_root, case_id)
        state = _inject_s5_artifacts(state, specialist_artifact_root, case_id)
        state = _inject_s6_aggregate(state)
        result = graph.invoke(state, config={"configurable": {"thread_id": f"{run_id}-{case_id}-s6-s8"}})
        score = _score_case(
            case,
            result,
            specialist_case_score=case_scores_by_id.get(case_id) or {},
            elapsed_sec=round(time.time() - case_started, 4),
            ordinal=ordinal,
            total=len(cases),
        )
        (case_dir / "judgment_memo_case_score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "judgment_memo_result_summary.json").write_text(
            json.dumps(_result_summary(result, score), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        scores.append(score)

    summary = _aggregate(
        run_id=run_id,
        args=args,
        specialist_summary=specialist_summary,
        scores=scores,
        elapsed_sec=round(time.time() - started, 4),
        output_dir=output_dir,
    )
    summary_path = output_dir / "judgment_memo_diagnostic.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_stdout_summary(summary, summary_path), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _graph_env(args: argparse.Namespace) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "LLM_BACKEND": args.llm_backend,
            "BASE_URL": args.base_url,
            "CHAT_COMPLETIONS_PATH": args.chat_completions_path,
            "MODEL_NAME": args.model,
            "API_KEY_ENV": args.api_key_env,
            "SEC_AGENT_MULTI_AGENT_MEMO_ROUTER": "llm",
            "MEMO_TEMPERATURE": str(args.temperature),
            "MEMO_MAX_TOKENS": str(args.memo_max_tokens),
            "VERIFIER_MAX_TOKENS": str(args.verifier_max_tokens),
            "MEMO_TIMEOUT_S": str(args.timeout_s),
            "MEMO_MAX_REPAIR_ATTEMPTS": str(args.max_repair_attempts),
        }
    )
    return env


def _inject_s5_artifacts(state: dict[str, Any], specialist_artifact_root: Path, case_id: str) -> dict[str, Any]:
    result = _read_json(specialist_artifact_root / case_id / "specialist_layer_result_summary.json")
    return {
        **state,
        "status": "running",
        "native_stop_after_node": "",
        "specialist_outputs": [dict(row) for row in result.get("specialist_outputs") or [] if isinstance(row, Mapping)],
        "specialist_route_results": [dict(row) for row in result.get("specialist_route_results") or [] if isinstance(row, Mapping)],
    }


def _inject_s6_aggregate(state: dict[str, Any]) -> dict[str, Any]:
    specialist_outputs = [dict(row) for row in state.get("specialist_outputs") or [] if isinstance(row, Mapping)]
    reflection = state.get("multi_agent_reflection_report") or state.get("evidence_sufficiency_report") or {}
    judgment = aggregate_specialist_judgment_plan(
        specialist_outputs,
        reflection_report=reflection if isinstance(reflection, Mapping) else {},
        evidence_requirement_plan=state.get("evidence_requirement_plan") or {},
        source_gaps=state.get("source_gaps") or [],
        tool_ledger_summary=_tool_ledger_summary(state),
        verifier_constraints=state.get("claim_verification") or {},
    )
    specialist_verification = verify_specialist_outputs_for_memo(specialist_outputs, judgment_plan=judgment)
    return {
        **state,
        "judgment_plan": judgment,
        "specialist_verification": specialist_verification,
        "verified_judgment_plan": specialist_verification.get("verified_judgment_plan") or judgment,
        "quality_second_pass_attempted": True,
        "multi_agent_second_pass_decision": {"allowed": False, "reason": "s6_s8_gate_reuses_passed_s5_artifacts"},
        "s6_aggregate_source": "diagnostic_runner_from_passed_s5_artifacts",
    }


def _tool_ledger_summary(state: Mapping[str, Any]) -> dict[str, Any]:
    ledger = state.get("tool_call_ledger") if isinstance(state.get("tool_call_ledger"), Mapping) else {}
    entries = [row for row in ledger.get("entries") or [] if isinstance(row, Mapping)]
    return {
        "tool_call_count": len(entries),
        "source_gap_count": len(state.get("source_gaps") or []),
        "ledger_status": str(ledger.get("status") or ""),
        "loop_break_reason": str(state.get("loop_break_reason") or ledger.get("loop_break_reason") or ""),
    }


def _score_case(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    specialist_case_score: Mapping[str, Any],
    elapsed_sec: float,
    ordinal: int,
    total: int,
) -> dict[str, Any]:
    judgment = result.get("verified_judgment_plan") if isinstance(result.get("verified_judgment_plan"), Mapping) else result.get("judgment_plan") or {}
    memo = result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else {}
    claim_verification = result.get("claim_verification") if isinstance(result.get("claim_verification"), Mapping) else {}
    memo_route = result.get("memo_route_result") if isinstance(result.get("memo_route_result"), Mapping) else {}
    memo_claims = [row for row in memo.get("memo_claims") or [] if isinstance(row, Mapping)]
    thesis_plan = memo.get("memo_thesis_plan") if isinstance(memo.get("memo_thesis_plan"), Mapping) else {}
    judgment_thesis_plan = judgment.get("memo_thesis_plan") if isinstance(judgment, Mapping) and isinstance(judgment.get("memo_thesis_plan"), Mapping) else {}
    supported_claim_count = len(judgment.get("supported_claims") or []) if isinstance(judgment, Mapping) else 0
    minimum_memo_claim_count = 3 if supported_claim_count >= 3 else 1
    checks = {
        "graph_stopped_after_verifier": result.get("status") == "stopped_after_node" and result.get("native_stop_after_node") == "verifier",
        "s5_specialist_case_passed": str(specialist_case_score.get("status") or "") == "pass",
        "judgment_plan_present": bool(judgment),
        "s6_aggregate_supported_claims_present": len(judgment.get("supported_claims") or []) > 0 if isinstance(judgment, Mapping) else False,
        "memo_thesis_plan_present": bool(judgment_thesis_plan),
        "memo_thesis_pack_present": bool((judgment or {}).get("memo_thesis_pack") if isinstance(judgment, Mapping) else False),
        "memo_thesis_pack_ready": str(((judgment or {}).get("memo_thesis_pack") or {}).get("status") or "") == "ready"
        if isinstance(judgment, Mapping) and isinstance((judgment or {}).get("memo_thesis_pack"), Mapping)
        else False,
        "memo_writer_allowed": bool((judgment or {}).get("memo_writer_allowed", True)) if isinstance(judgment, Mapping) else False,
        "memo_route_pass": str(memo_route.get("status") or "") == "pass",
        "memo_not_fallback": str(memo.get("llm_route_source") or "").endswith("+deterministic_fallback") is False,
        "memo_claims_present": bool(memo_claims),
        "memo_claim_count_min_when_ready": len(memo_claims) >= minimum_memo_claim_count if minimum_memo_claim_count > 1 else bool(memo_claims),
        "memo_thesis_plan_carried": bool(thesis_plan) and str(thesis_plan.get("primary_thesis_claim_id") or "") == str(judgment_thesis_plan.get("primary_thesis_claim_id") or ""),
        "memo_raw_rows_not_consumed": memo.get("raw_rows_consumed") is False,
        "memo_tool_calls_not_requested": not memo.get("tool_calls_requested"),
        "verifier_pass": str(claim_verification.get("status") or "") == "pass",
    }
    return {
        "case_id": case.get("case_id"),
        "ordinal": ordinal,
        "total": total,
        "prompt": case.get("prompt") or "",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "judgment_metrics": _judgment_metrics(judgment),
        "memo_metrics": _memo_metrics(memo),
        "token_usage": _token_usage(result),
        "memo_route_result": {
            "status": memo_route.get("status") or "",
            "attempt_count": int(memo_route.get("attempt_count") or 0),
            "repair_attempts": int(memo_route.get("repair_attempts") or 0),
            "finish_reasons": memo_route.get("finish_reasons") or [],
            "total_tokens": int(memo_route.get("total_tokens") or 0),
        },
        "claim_verification_status": claim_verification.get("status") or "",
        "claim_verification_error_count": len(claim_verification.get("errors") or []),
    }


def _judgment_metrics(judgment: Any) -> dict[str, Any]:
    if not isinstance(judgment, Mapping):
        return {}
    pack = judgment.get("memo_thesis_pack") if isinstance(judgment.get("memo_thesis_pack"), Mapping) else {}
    return {
        "status": judgment.get("status") or "",
        "supported_claim_count": len(judgment.get("supported_claims") or []),
        "unsupported_claim_count": len(judgment.get("unsupported_claims") or []),
        "conflict_count": len(judgment.get("conflicts") or []),
        "memo_outline_count": len(judgment.get("memo_outline") or []),
        "claim_card_stats": dict(judgment.get("claim_card_stats") or {}),
        "memo_thesis_pack_status": pack.get("status") or "",
        "memo_thesis_pack_driver_count": len(pack.get("supporting_drivers") or []),
        "memo_thesis_pack_counterargument_count": len(pack.get("counterarguments") or []),
    }


def _memo_metrics(memo: Mapping[str, Any]) -> dict[str, Any]:
    claims = [row for row in memo.get("memo_claims") or [] if isinstance(row, Mapping)]
    refs = sorted({str(ref) for row in claims for ref in row.get("evidence_refs") or [] if str(ref or "").strip()})
    return {
        "answer_status": memo.get("answer_status") or "",
        "direct_answer_chars": len(str(memo.get("direct_answer") or "")),
        "memo_claim_count": len(claims),
        "memo_claim_evidence_ref_count": len(refs),
        "caveat_count": len(memo.get("caveats") or []),
        "unsupported_claims_excluded_count": len(memo.get("unsupported_claims_excluded") or []),
        "source_boundary_note_count": len(memo.get("source_boundary_notes") or []),
        "raw_rows_consumed": bool(memo.get("raw_rows_consumed")),
        "tool_call_count": len(memo.get("tool_calls_requested") or []),
        "llm_route_source": memo.get("llm_route_source") or "",
    }


def _token_usage(result: Mapping[str, Any]) -> dict[str, int]:
    memo_route = result.get("memo_route_result") if isinstance(result.get("memo_route_result"), Mapping) else {}
    claim = result.get("claim_verification") if isinstance(result.get("claim_verification"), Mapping) else {}
    verifier_diag = claim.get("model_diagnostics") if isinstance(claim.get("model_diagnostics"), Mapping) else {}
    verifier_calls = [row for row in verifier_diag.get("calls") or [] if isinstance(row, Mapping)]
    verifier_tokens = sum(int(row.get("total_tokens") or 0) for row in verifier_calls)
    memo_tokens = int(memo_route.get("total_tokens") or 0)
    return {
        "memo_writer_tokens": memo_tokens,
        "verifier_tokens": verifier_tokens,
        "total_tokens": memo_tokens + verifier_tokens,
    }


def _result_summary(result: Mapping[str, Any], score: Mapping[str, Any]) -> dict[str, Any]:
    memo = result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else {}
    claim = result.get("claim_verification") if isinstance(result.get("claim_verification"), Mapping) else {}
    judgment = result.get("verified_judgment_plan") if isinstance(result.get("verified_judgment_plan"), Mapping) else result.get("judgment_plan") or {}
    return {
        "status": result.get("status") or "",
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "s6_aggregate_source": result.get("s6_aggregate_source") or "",
        "node_trace": result.get("node_trace") or [],
        "judgment_metrics": score.get("judgment_metrics") or {},
        "memo_metrics": score.get("memo_metrics") or {},
        "memo_route_result": result.get("memo_route_result") or {},
        "memo_answer": _compact_memo_for_summary(memo),
        "claim_verification": _compact_claim_verification_for_summary(claim),
        "verified_judgment_plan": _compact_judgment_for_summary(judgment),
    }


def _compact_memo_for_summary(memo: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "answer_status": memo.get("answer_status") or "",
        "direct_answer": str(memo.get("direct_answer") or "")[:1200],
        "memo_claims": [dict(row) for row in memo.get("memo_claims") or [] if isinstance(row, Mapping)][:6],
        "caveats": [dict(row) if isinstance(row, Mapping) else row for row in memo.get("caveats") or []][:4],
        "unsupported_claims_excluded": [
            dict(row) if isinstance(row, Mapping) else row for row in memo.get("unsupported_claims_excluded") or []
        ][:4],
        "source_boundary_notes": [dict(row) if isinstance(row, Mapping) else row for row in memo.get("source_boundary_notes") or []][:4],
        "memo_thesis_plan": dict(memo.get("memo_thesis_plan") or {}) if isinstance(memo.get("memo_thesis_plan"), Mapping) else {},
        "source_boundary": memo.get("source_boundary") or "",
        "llm_route_source": memo.get("llm_route_source") or "",
    }


def _compact_claim_verification_for_summary(claim: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": claim.get("status") or "",
        "error_count": len(claim.get("errors") or []),
        "errors": [dict(row) for row in claim.get("errors") or [] if isinstance(row, Mapping)][:6],
        "warnings": [dict(row) for row in claim.get("warnings") or [] if isinstance(row, Mapping)][:6],
        "repair_instruction": str(claim.get("repair_instruction") or "")[:500],
        "bounded_answer_allowed": bool(claim.get("bounded_answer_allowed")),
        "verifier_input_projection": dict(claim.get("verifier_input_projection") or {})
        if isinstance(claim.get("verifier_input_projection"), Mapping)
        else {},
    }


def _compact_judgment_for_summary(judgment: Any) -> dict[str, Any]:
    if not isinstance(judgment, Mapping):
        return {}
    return {
        "status": judgment.get("status") or "",
        "memo_writer_allowed": bool(judgment.get("memo_writer_allowed", True)),
        "memo_thesis_plan": dict(judgment.get("memo_thesis_plan") or {}) if isinstance(judgment.get("memo_thesis_plan"), Mapping) else {},
        "memo_thesis_pack": dict(judgment.get("memo_thesis_pack") or {}) if isinstance(judgment.get("memo_thesis_pack"), Mapping) else {},
        "claim_card_stats": dict(judgment.get("claim_card_stats") or {}),
        "unsupported_claim_policy": dict(judgment.get("unsupported_claim_policy") or {})
        if isinstance(judgment.get("unsupported_claim_policy"), Mapping)
        else {},
    }


def _aggregate(
    *,
    run_id: str,
    args: argparse.Namespace,
    specialist_summary: Mapping[str, Any],
    scores: list[dict[str, Any]],
    elapsed_sec: float,
    output_dir: Path,
) -> dict[str, Any]:
    pass_count = sum(1 for score in scores if score.get("status") == "pass")
    token_usage = {
        "memo_writer_tokens": sum(int((score.get("token_usage") or {}).get("memo_writer_tokens") or 0) for score in scores),
        "verifier_tokens": sum(int((score.get("token_usage") or {}).get("verifier_tokens") or 0) for score in scores),
        "total_tokens": sum(int((score.get("token_usage") or {}).get("total_tokens") or 0) for score in scores),
    }
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": elapsed_sec,
        "gate_status": "pass" if scores and pass_count == len(scores) else "fail",
        "diagnostic_only": True,
        "specialist_summary": str(args.specialist_summary.resolve()),
        "specialist_run_id": specialist_summary.get("run_id") or "",
        "output_dir": str(output_dir.resolve()),
        "model_config": {
            "llm_backend": args.llm_backend,
            "base_url": args.base_url,
            "chat_completions_path": args.chat_completions_path,
            "model": args.model,
            "api_key_env": args.api_key_env,
            "api_key_saved": False,
            "temperature": args.temperature,
            "memo_max_tokens": args.memo_max_tokens,
            "verifier_max_tokens": args.verifier_max_tokens,
            "timeout_s": args.timeout_s,
            "max_repair_attempts": args.max_repair_attempts,
        },
        "metrics": {
            "case_count": len(scores),
            "pass_count": pass_count,
            "failed_count": len(scores) - pass_count,
            "memo_route_pass_case_count": sum(1 for score in scores if (score.get("checks") or {}).get("memo_route_pass")),
            "verifier_pass_case_count": sum(1 for score in scores if (score.get("checks") or {}).get("verifier_pass")),
            "token_usage": token_usage,
            "memo_repair_attempts_total": sum(int((score.get("memo_route_result") or {}).get("repair_attempts") or 0) for score in scores),
        },
        "cases": scores,
        "failed_cases": [
            {"case_id": score.get("case_id"), "checks": score.get("checks"), "memo_metrics": score.get("memo_metrics")}
            for score in scores
            if score.get("status") != "pass"
        ],
    }


def _stdout_summary(summary: Mapping[str, Any], path: Path) -> dict[str, Any]:
    return {
        "run_id": summary.get("run_id"),
        "gate_status": summary.get("gate_status"),
        "output_path": str(path.resolve()),
        "metrics": summary.get("metrics") or {},
        "failed_cases": summary.get("failed_cases") or [],
    }


def _default_run_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d')}_fin_agent_s6_s8_judgment_memo_gate_v0_1"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
