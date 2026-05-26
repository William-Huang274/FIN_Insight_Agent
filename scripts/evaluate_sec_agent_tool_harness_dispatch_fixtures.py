from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.graph_state import ARTIFACT_KEYS, SecAgentState  # noqa: E402
from sec_agent.tool_harness import SESSION_SCHEMA_VERSION, SecAgentToolHarness  # noqa: E402


DEFAULT_FIXTURE_ROOT = REPO_ROOT / "reports" / "quality" / "local_tool_harness_dispatch_fixture_runtime"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "quality" / "local_tool_harness_dispatch_fixtures_v1.json"

COMPLETED_SESSION_ID = "fixture_dispatch_completed"
COMPLETED_USER_ID = "fixture_user_completed"
COMPLETED_TENANT_ID = "fixture_tenant"
COMPLETED_ANSWER_ID = "fixture_ans_msft_aapl_2025"
ALT_COMPLETED_SESSION_ID = "fixture_dispatch_completed_alt"
ALT_COMPLETED_USER_ID = "fixture_user_completed_alt"
ALT_COMPLETED_ANSWER_ID = "fixture_ans_amzn_meta_2025"
PARTIAL_SESSION_ID = "fixture_dispatch_partial"
PARTIAL_USER_ID = "fixture_user_partial"
PARTIAL_ANSWER_ID = "fixture_ans_amzn_meta_partial"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fixture-backed dispatch checks for the SEC agent tool harness.")
    parser.add_argument("--fixture-root", default=str(DEFAULT_FIXTURE_ROOT))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--keep-fixtures", action="store_true", default=True)
    parser.add_argument("--clean-fixtures", dest="keep_fixtures", action="store_false")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    fixture_root = Path(args.fixture_root).resolve()
    _prepare_fixture_root(fixture_root)

    completed = _write_completed_fixture(fixture_root)
    completed_alt = _write_completed_alt_fixture(fixture_root)
    partial = _write_partial_fixture(fixture_root)
    harness = SecAgentToolHarness(
        session_root=fixture_root / "session_harness",
        python="__sec_agent_fixture_should_not_execute__",
        repo_root=REPO_ROOT,
    )

    cases: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("inspect_coverage_reads_existing_matrix", lambda: _case_inspect_coverage(harness, completed)),
        ("explain_evidence_reads_answer_ledger_and_plan", lambda: _case_explain_evidence(harness, completed)),
        ("explain_evidence_falls_back_to_memo_section_ordinal", lambda: _case_explain_evidence_section_ordinal(harness, completed)),
        ("explain_evidence_resolves_claim_reference", lambda: _case_explain_evidence_claim_reference(harness, completed)),
        ("resume_analysis_reports_first_missing_node_without_execute", lambda: _case_resume_analysis(harness, partial)),
        ("reformat_answer_records_request_only", lambda: _case_reformat_answer(harness, completed)),
        ("get_session_state_enforces_user_boundary", lambda: _case_get_session_state_user_boundary(harness, completed)),
        ("get_session_state_reads_alt_session_without_leakage", lambda: _case_get_session_state_alt_isolated(harness, completed_alt)),
        ("inspect_coverage_reads_alt_session_without_leakage", lambda: _case_inspect_coverage_alt_isolated(harness, completed_alt)),
        ("explain_evidence_resolves_alt_amzn_ads_claim", lambda: _case_explain_evidence_alt_claim_reference(harness, completed_alt)),
        ("get_session_state_enforces_alt_user_boundary", lambda: _case_get_session_state_alt_user_boundary(harness, completed_alt)),
    ]

    case_results = [_run_case(name, func) for name, func in cases]
    failures = [case for case in case_results if not case["passed"]]
    summary = {
        "schema_version": "sec_agent_tool_harness_dispatch_fixture_eval_v0.1",
        "run_id": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_tool_harness_dispatch_fixtures_v1",
        "fixture_root": str(fixture_root),
        "case_count": len(case_results),
        "passed_count": sum(1 for case in case_results if case["passed"]),
        "failed_count": len(failures),
        "all_pass": not failures,
        "cases": case_results,
        "fixtures": {
            "completed_session_id": COMPLETED_SESSION_ID,
            "completed_answer_id": COMPLETED_ANSWER_ID,
            "alt_completed_session_id": ALT_COMPLETED_SESSION_ID,
            "alt_completed_answer_id": ALT_COMPLETED_ANSWER_ID,
            "partial_session_id": PARTIAL_SESSION_ID,
            "partial_answer_id": PARTIAL_ANSWER_ID,
        },
    }

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.keep_fixtures:
        _safe_rmtree(fixture_root)
    print(json.dumps({key: summary[key] for key in _SUMMARY_KEYS}, ensure_ascii=False, indent=2))
    return 0 if summary["all_pass"] else 1


_SUMMARY_KEYS = (
    "run_id",
    "fixture_root",
    "case_count",
    "passed_count",
    "failed_count",
    "all_pass",
)


def _run_case(name: str, func: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        details = func()
        return {"case_id": name, "passed": True, "details": details}
    except Exception as exc:
        return {
            "case_id": name,
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _case_inspect_coverage(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "inspect_coverage",
        {"session_id": COMPLETED_SESSION_ID, "answer_id": COMPLETED_ANSWER_ID},
    ).to_dict()
    payload = result["payload"]
    _assert(result["status"] == "completed", "inspect_coverage should complete")
    _assert(payload["rerun_required"] is False, "inspect_coverage must not request rerun")
    _assert(payload["task_count"] == 2, "coverage fixture should expose two tasks")
    _assert(payload["summary"]["coverage_complete"] is True, "coverage summary should be complete")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count + 1, "inspect turn should be recorded")
    return {
        "tool_status": result["status"],
        "task_count": payload["task_count"],
        "rerun_required": payload["rerun_required"],
        "turn_count_delta": 1,
    }


def _case_explain_evidence(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "explain_evidence",
        {"session_id": COMPLETED_SESSION_ID, "answer_id": COMPLETED_ANSWER_ID, "driver_index": 1},
    ).to_dict()
    payload = result["payload"]
    _assert(result["status"] == "completed", "explain_evidence should complete")
    _assert(payload["rerun_required"] is False, "explain_evidence must not request rerun")
    _assert("fixture_msft_cloud_revenue_2025" in payload["metric_ids"], "driver metric id should be resolved")
    _assert("fixture_ev_msft_cloud_2025" in payload["evidence_ids"], "driver evidence id should be resolved")
    _assert(len(payload["ledger_matches"]) == 1, "exactly one ledger row should match driver 1")
    _assert(len(payload["judgment_plan_matches"]) == 1, "exactly one Judgment Plan driver should match")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count + 1, "explain turn should be recorded")
    return {
        "tool_status": result["status"],
        "metric_ids": payload["metric_ids"],
        "evidence_ids": payload["evidence_ids"],
        "ledger_match_count": len(payload["ledger_matches"]),
        "judgment_plan_match_count": len(payload["judgment_plan_matches"]),
        "rerun_required": payload["rerun_required"],
    }


def _case_explain_evidence_section_ordinal(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "explain_evidence",
        {"session_id": COMPLETED_SESSION_ID, "answer_id": COMPLETED_ANSWER_ID, "driver_index": 2},
    ).to_dict()
    payload = result["payload"]
    target = payload["target"]
    _assert(result["status"] == "completed", "section-aware explain_evidence should complete")
    _assert(target["section"] == "why_it_matters", "driver_index fallback should resolve against why_it_matters")
    _assert(target["index"] == 2, "fallback should preserve the requested ordinal")
    _assert("fixture_aapl_gross_margin_2025" in payload["metric_ids"], "section ordinal should resolve margin metric id")
    _assert("fixture_ev_aapl_margin_2025" in payload["evidence_ids"], "section ordinal should resolve margin evidence id")
    _assert(len(payload["ledger_matches"]) == 1, "section ordinal should match one ledger row")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count + 1, "explain turn should be recorded")
    return {
        "tool_status": result["status"],
        "target": target,
        "metric_ids": payload["metric_ids"],
        "evidence_ids": payload["evidence_ids"],
        "ledger_match_count": len(payload["ledger_matches"]),
    }


def _case_explain_evidence_claim_reference(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "explain_evidence",
        {
            "session_id": COMPLETED_SESSION_ID,
            "answer_id": COMPLETED_ANSWER_ID,
            "claim_reference": "解释一下 memo 里毛利率改善那条证据，不要重新跑。",
        },
    ).to_dict()
    payload = result["payload"]
    target = payload["target"]
    _assert(result["status"] == "completed", "claim-reference explain_evidence should complete")
    _assert(target["section"] in {"why_it_matters", "what_changed", "decision_drivers"}, "target section should be evidence-bearing")
    _assert("fixture_aapl_gross_margin_2025" in payload["metric_ids"], "claim reference should resolve margin metric id")
    _assert("fixture_ev_aapl_margin_2025" in payload["evidence_ids"], "claim reference should resolve margin evidence id")
    _assert(len(payload["ledger_matches"]) == 1, "claim reference should match one ledger row")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count + 1, "explain turn should be recorded")
    return {
        "tool_status": result["status"],
        "target": target,
        "metric_ids": payload["metric_ids"],
        "evidence_ids": payload["evidence_ids"],
        "ledger_match_count": len(payload["ledger_matches"]),
    }


def _case_resume_analysis(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "resume_analysis",
        {"session_id": PARTIAL_SESSION_ID, "answer_id": PARTIAL_ANSWER_ID, "execute": False},
    ).to_dict()
    payload = result["payload"]
    report = payload["resume_report"]
    _assert(result["status"] == "completed", "resume_analysis should complete")
    _assert(payload["execute"] is False, "fixture resume must not execute graph runner")
    _assert("returncode" not in payload, "resume_analysis execute=false must not spawn graph runner")
    _assert(report["next_ready_node"] == "build_coverage_matrix", "partial fixture should resume at coverage")
    _assert("query_contract" in report["complete_artifacts"], "query_contract should be preserved")
    _assert("retrieved_context" in report["complete_artifacts"], "retrieved_context should be preserved")
    _assert("runtime_exact_value_ledger" in report["complete_artifacts"], "ledger should be preserved")
    _assert("evidence_coverage_matrix" in report["missing_artifacts"], "coverage should be missing")
    _assert("judgment_plan" in report["missing_artifacts"], "Judgment Plan should be missing")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count + 1, "resume turn should be recorded")
    return {
        "tool_status": result["status"],
        "next_ready_node": report["next_ready_node"],
        "complete_artifacts": report["complete_artifacts"],
        "missing_artifacts": report["missing_artifacts"],
        "execute": payload["execute"],
    }


def _case_reformat_answer(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "reformat_answer",
        {
            "session_id": COMPLETED_SESSION_ID,
            "answer_id": COMPLETED_ANSWER_ID,
            "format": "pm_5_bullets",
            "preserve_citations": True,
            "execute": False,
        },
    ).to_dict()
    payload = result["payload"]
    request_path = Path(payload["request_path"])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    _assert(result["status"] == "planned", "reformat_answer v0 should be planned")
    _assert(payload["execute_supported"] is False, "v0 reformat execution should remain disabled")
    _assert(payload["invalidated_artifacts"] == ["rendered_answer"], "only rendered_answer should be invalidated")
    _assert(request["format"] == "pm_5_bullets", "reformat request should preserve canonical format")
    _assert(request["preserve_citations"] is True, "reformat request should preserve citations")
    _assert(request["execute"] is False, "fixture reformat must not execute synthesis")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count + 1, "reformat turn should be recorded")
    return {
        "tool_status": result["status"],
        "request_path": str(request_path),
        "invalidated_artifacts": payload["invalidated_artifacts"],
        "execute_supported": payload["execute_supported"],
    }


def _case_get_session_state_user_boundary(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "get_session_state",
        {"session_id": COMPLETED_SESSION_ID, "user_id": "wrong_user"},
    ).to_dict()
    _assert(result["status"] == "error", "wrong user should be rejected")
    _assert("user_id does not match" in result["message"], "error should explain user boundary")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count, "failed state read should not append a turn")
    return {"tool_status": result["status"], "message": result["message"]}


def _case_get_session_state_alt_isolated(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "get_session_state",
        {"session_id": ALT_COMPLETED_SESSION_ID, "user_id": ALT_COMPLETED_USER_ID},
    ).to_dict()
    payload = result["payload"]
    scope = payload["active_scope"]
    scope_text = json.dumps(payload, ensure_ascii=False)
    _assert(result["status"] == "completed", "alt session state should complete")
    _assert(payload["active_answer_id"] == ALT_COMPLETED_ANSWER_ID, "alt active answer should be returned")
    _assert(sorted(scope["selected_tickers"]) == ["AMZN", "META"], "alt scope should expose only AMZN/META")
    _assert("MSFT" not in scope_text and "AAPL" not in scope_text and "NVDA" not in scope_text, "other session tickers should not leak")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count, "state read should not append a turn")
    return {
        "tool_status": result["status"],
        "active_answer_id": payload["active_answer_id"],
        "active_scope": scope,
    }


def _case_inspect_coverage_alt_isolated(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "inspect_coverage",
        {"session_id": ALT_COMPLETED_SESSION_ID, "answer_id": ALT_COMPLETED_ANSWER_ID},
    ).to_dict()
    payload = result["payload"]
    tasks_text = json.dumps(payload["tasks"], ensure_ascii=False)
    _assert(result["status"] == "completed", "alt inspect_coverage should complete")
    _assert(payload["rerun_required"] is False, "alt coverage must not request rerun")
    _assert(payload["task_count"] == 3, "alt coverage fixture should expose three tasks")
    _assert(payload["summary"]["coverage_complete"] is True, "alt coverage summary should be complete")
    _assert("AMZN" in tasks_text and "META" in tasks_text, "alt coverage should include AMZN/META")
    _assert("MSFT" not in tasks_text and "AAPL" not in tasks_text and "NVDA" not in tasks_text, "other session coverage should not leak")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count + 1, "alt inspect turn should be recorded")
    return {
        "tool_status": result["status"],
        "task_count": payload["task_count"],
        "summary": payload["summary"],
        "rerun_required": payload["rerun_required"],
    }


def _case_explain_evidence_alt_claim_reference(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "explain_evidence",
        {
            "session_id": ALT_COMPLETED_SESSION_ID,
            "answer_id": ALT_COMPLETED_ANSWER_ID,
            "claim_reference": "解释 AMZN 广告业务增长那条证据，从哪个 10-K 片段来的？",
        },
    ).to_dict()
    payload = result["payload"]
    target = payload["target"]
    _assert(result["status"] == "completed", "alt claim-reference explain_evidence should complete")
    _assert(target["section"] in {"why_it_matters", "decision_drivers", "what_changed"}, "alt target section should be evidence-bearing")
    _assert("fixture_amzn_advertising_revenue_2025" in payload["metric_ids"], "AMZN ads metric id should resolve")
    _assert("fixture_ev_amzn_ads_2025" in payload["evidence_ids"], "AMZN ads evidence id should resolve")
    _assert(len(payload["ledger_matches"]) == 1, "alt claim reference should match one ledger row")
    _assert(len(payload["judgment_plan_matches"]) == 1, "alt claim reference should match one Judgment Plan driver")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count + 1, "alt explain turn should be recorded")
    return {
        "tool_status": result["status"],
        "target": target,
        "metric_ids": payload["metric_ids"],
        "evidence_ids": payload["evidence_ids"],
        "ledger_match_count": len(payload["ledger_matches"]),
        "judgment_plan_match_count": len(payload["judgment_plan_matches"]),
    }


def _case_get_session_state_alt_user_boundary(harness: SecAgentToolHarness, fixture: dict[str, Any]) -> dict[str, Any]:
    before_turn_count = _session_turn_count(fixture["session_path"])
    result = harness.dispatch(
        "get_session_state",
        {"session_id": ALT_COMPLETED_SESSION_ID, "user_id": COMPLETED_USER_ID},
    ).to_dict()
    _assert(result["status"] == "error", "wrong alt user should be rejected")
    _assert("user_id does not match" in result["message"], "alt error should explain user boundary")
    _assert(_session_turn_count(fixture["session_path"]) == before_turn_count, "failed alt state read should not append a turn")
    return {"tool_status": result["status"], "message": result["message"]}


def _write_completed_fixture(fixture_root: Path) -> dict[str, Any]:
    run_root = fixture_root / "runs" / "completed_msft_aapl"
    session_root = fixture_root / "session_harness"
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "qwen").mkdir(parents=True, exist_ok=True)

    files = {
        "query_contract": _write_json(
            run_root / "query_contract.json",
            {
                "schema_version": "fixture_query_contract_v0.1",
                "case_id": COMPLETED_ANSWER_ID,
                "task_type": "investment_memo",
                "focus_tickers": ["MSFT", "AAPL"],
                "years": [2025],
            },
        ),
        "retrieved_context": _write_jsonl(
            run_root / "retrieved_context.jsonl",
            [
                {
                    "object_id": "fixture_ev_msft_cloud_2025",
                    "ticker": "MSFT",
                    "year": 2025,
                    "section": "Item 7",
                    "text": "Microsoft cloud and AI demand fixture snippet.",
                },
                {
                    "object_id": "fixture_ev_aapl_margin_2025",
                    "ticker": "AAPL",
                    "year": 2025,
                    "section": "Item 7",
                    "text": "Apple gross margin fixture snippet.",
                },
            ],
        ),
        "runtime_exact_value_ledger": _write_json(
            run_root / "runtime_exact_value_ledger.json",
            {
                "schema_version": "fixture_runtime_exact_value_ledger_v0.1",
                "rows": [
                    {
                        "metric_id": "fixture_msft_cloud_revenue_2025",
                        "ticker": "MSFT",
                        "fiscal_year": 2025,
                        "metric_name": "cloud revenue",
                        "value": 100000,
                        "unit": "usd_millions",
                        "source_evidence_id": "fixture_ev_msft_cloud_2025",
                        "object_id": "fixture_ev_msft_cloud_2025",
                        "preview": "Cloud revenue fixture row.",
                    },
                    {
                        "metric_id": "fixture_aapl_gross_margin_2025",
                        "ticker": "AAPL",
                        "fiscal_year": 2025,
                        "metric_name": "gross margin",
                        "value": 46.5,
                        "unit": "percent",
                        "source_evidence_id": "fixture_ev_aapl_margin_2025",
                        "object_id": "fixture_ev_aapl_margin_2025",
                        "preview": "Gross margin fixture row.",
                    },
                ],
            },
        ),
        "evidence_coverage_matrix": _write_json(
            run_root / "runtime_evidence_coverage_matrix.json",
            {
                "schema_version": "sec_agent_evidence_coverage_matrix_v0.1",
                "case_id": COMPLETED_ANSWER_ID,
                "tasks": [
                    {
                        "task_id": "task_msft_cloud",
                        "required_tickers": ["MSFT"],
                        "covered_tickers": ["MSFT"],
                        "missing_tickers": [],
                        "covered_metric_families": ["cloud_revenue"],
                        "missing_metric_families": [],
                        "coverage_complete": True,
                        "answer_status": "complete",
                    },
                    {
                        "task_id": "task_aapl_margin",
                        "required_tickers": ["AAPL"],
                        "covered_tickers": ["AAPL"],
                        "missing_tickers": [],
                        "covered_metric_families": ["gross_margin"],
                        "missing_metric_families": [],
                        "coverage_complete": True,
                        "answer_status": "complete",
                    },
                ],
                "summary": {
                    "task_count": 2,
                    "coverage_complete": True,
                    "answer_status": "complete",
                    "covered_focus_tickers": ["AAPL", "MSFT"],
                    "missing_metric_families": [],
                    "ledger_row_count": 2,
                    "context_row_count": 2,
                },
            },
        ),
        "judgment_plan": _write_json(
            run_root / "runtime_judgment_plan.json",
            {
                "schema_version": "fixture_runtime_judgment_plan_v0.1",
                "plans": [
                    {
                        "case_id": COMPLETED_ANSWER_ID,
                        "decision_drivers": [
                            {
                                "driver_id": "jp_driver_msft_cloud",
                                "driver_claim": "MSFT cloud growth is supported by SEC 10-K evidence.",
                                "supporting_metric_ids": ["fixture_msft_cloud_revenue_2025"],
                                "supporting_evidence_ids": ["fixture_ev_msft_cloud_2025"],
                            },
                            {
                                "driver_id": "jp_driver_aapl_margin",
                                "driver_claim": "AAPL margin context is supported by SEC 10-K evidence.",
                                "supporting_metric_ids": ["fixture_aapl_gross_margin_2025"],
                                "supporting_evidence_ids": ["fixture_ev_aapl_margin_2025"],
                            },
                        ],
                    }
                ],
            },
        ),
        "evidence_pack": _write_json(run_root / "evidence_pack.json", {"schema_version": "fixture_evidence_pack_v0.1"}),
        "memo_answer": _write_jsonl(
            run_root / "qwen" / "agent_outputs.jsonl",
            [
                {
                    "schema_version": "fixture_agent_output_v0.1",
                    "case_id": COMPLETED_ANSWER_ID,
                    "status": "answered",
                    "answer": {
                        "summary": "Fixture memo summary.",
                        "decision_drivers": [
                            {
                                "driver_claim": "MSFT cloud revenue supports the growth driver.",
                                "why_it_matters": "Cloud revenue is central to the AI demand thesis.",
                                "supporting_metric_ids": ["fixture_msft_cloud_revenue_2025"],
                                "supporting_evidence_ids": ["fixture_ev_msft_cloud_2025"],
                                "conclusion_strength": "medium",
                            }
                        ],
                        "why_it_matters": [
                            {
                                "insight": "MSFT cloud growth supports the main growth driver.",
                                "business_implication": "Cloud demand is central to the AI infrastructure thesis.",
                                "metric_ids": ["fixture_msft_cloud_revenue_2025"],
                                "evidence_ids": ["fixture_ev_msft_cloud_2025"],
                                "confidence": "high",
                            },
                            {
                                "insight": "AAPL gross margin improvement supports profitability context.",
                                "business_implication": "Gross margin trend affects quality of earnings and pricing power.",
                                "metric_ids": ["fixture_aapl_gross_margin_2025"],
                                "evidence_ids": ["fixture_ev_aapl_margin_2025"],
                                "confidence": "high",
                            },
                        ],
                        "what_changed": [
                            {
                                "claim": "AAPL gross margin improved in the fixture period.",
                                "metric_ids": ["fixture_aapl_gross_margin_2025"],
                                "evidence_ids": ["fixture_ev_aapl_margin_2025"],
                                "confidence": "high",
                            }
                        ],
                        "key_points": [],
                        "not_found": [],
                        "limitations": [],
                    },
                }
            ],
        ),
        "claim_verification": _write_json(run_root / "claim_verification.json", {"schema_version": "fixture_claim_verification_v0.1"}),
        "deterministic_gates": _write_json(run_root / "deterministic_gates.json", {"schema_version": "fixture_gates_v0.1", "all_pass": True}),
        "rendered_answer": _write_text(run_root / "rendered_answer.md", "# Fixture Memo\n"),
    }
    state_path = _write_state(run_root, COMPLETED_ANSWER_ID, "Fixture completed memo", ["MSFT", "AAPL"], [2025], files)
    session_path = _write_session(
        session_root=session_root,
        session_id=COMPLETED_SESSION_ID,
        user_id=COMPLETED_USER_ID,
        tenant_id=COMPLETED_TENANT_ID,
        active_answer_id=COMPLETED_ANSWER_ID,
        active_query="Fixture completed MSFT/AAPL 2025 memo",
        active_scope={"selected_tickers": ["MSFT", "AAPL"], "selected_years": [2025], "source_policy": "SEC_ONLY_10K"},
        analysis={
            "answer_id": COMPLETED_ANSWER_ID,
            "query": "Fixture completed MSFT/AAPL 2025 memo",
            "status": "completed",
            "run_root": str(run_root),
            "state_path": str(state_path),
            "artifact_refs": _state_artifact_refs(state_path),
            "invalidated_artifacts": [],
            "execution": {"execute": False, "returncode": 0, "elapsed_sec": 0.0},
        },
    )
    return {"run_root": run_root, "session_path": session_path, "state_path": state_path}


def _write_completed_alt_fixture(fixture_root: Path) -> dict[str, Any]:
    run_root = fixture_root / "runs" / "completed_amzn_meta"
    session_root = fixture_root / "session_harness"
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "qwen").mkdir(parents=True, exist_ok=True)

    files = {
        "query_contract": _write_json(
            run_root / "query_contract.json",
            {
                "schema_version": "fixture_query_contract_v0.1",
                "case_id": ALT_COMPLETED_ANSWER_ID,
                "task_type": "investment_memo",
                "focus_tickers": ["AMZN", "META"],
                "years": [2025],
            },
        ),
        "retrieved_context": _write_jsonl(
            run_root / "retrieved_context.jsonl",
            [
                {
                    "object_id": "fixture_ev_amzn_ads_2025",
                    "ticker": "AMZN",
                    "year": 2025,
                    "section": "Item 7",
                    "text": "Amazon advertising services revenue growth fixture snippet.",
                },
                {
                    "object_id": "fixture_ev_meta_ads_2025",
                    "ticker": "META",
                    "year": 2025,
                    "section": "Item 7",
                    "text": "Meta advertising revenue scale fixture snippet.",
                },
                {
                    "object_id": "fixture_ev_amzn_aws_2025",
                    "ticker": "AMZN",
                    "year": 2025,
                    "section": "Item 7",
                    "text": "AWS cloud services growth fixture snippet.",
                },
            ],
        ),
        "runtime_exact_value_ledger": _write_json(
            run_root / "runtime_exact_value_ledger.json",
            {
                "schema_version": "fixture_runtime_exact_value_ledger_v0.1",
                "rows": [
                    {
                        "metric_id": "fixture_amzn_advertising_revenue_2025",
                        "ticker": "AMZN",
                        "fiscal_year": 2025,
                        "metric_name": "advertising services revenue",
                        "value": 56000,
                        "unit": "usd_millions",
                        "source_evidence_id": "fixture_ev_amzn_ads_2025",
                        "object_id": "fixture_ev_amzn_ads_2025",
                        "preview": "AMZN advertising revenue fixture row.",
                    },
                    {
                        "metric_id": "fixture_meta_advertising_revenue_2025",
                        "ticker": "META",
                        "fiscal_year": 2025,
                        "metric_name": "advertising revenue",
                        "value": 164000,
                        "unit": "usd_millions",
                        "source_evidence_id": "fixture_ev_meta_ads_2025",
                        "object_id": "fixture_ev_meta_ads_2025",
                        "preview": "META advertising revenue fixture row.",
                    },
                    {
                        "metric_id": "fixture_amzn_aws_sales_2025",
                        "ticker": "AMZN",
                        "fiscal_year": 2025,
                        "metric_name": "AWS net sales",
                        "value": 108000,
                        "unit": "usd_millions",
                        "source_evidence_id": "fixture_ev_amzn_aws_2025",
                        "object_id": "fixture_ev_amzn_aws_2025",
                        "preview": "AWS sales fixture row.",
                    },
                ],
            },
        ),
        "evidence_coverage_matrix": _write_json(
            run_root / "runtime_evidence_coverage_matrix.json",
            {
                "schema_version": "sec_agent_evidence_coverage_matrix_v0.1",
                "case_id": ALT_COMPLETED_ANSWER_ID,
                "tasks": [
                    {
                        "task_id": "task_amzn_advertising",
                        "required_tickers": ["AMZN"],
                        "covered_tickers": ["AMZN"],
                        "missing_tickers": [],
                        "covered_metric_families": ["advertising"],
                        "missing_metric_families": [],
                        "coverage_complete": True,
                        "answer_status": "complete",
                    },
                    {
                        "task_id": "task_meta_advertising",
                        "required_tickers": ["META"],
                        "covered_tickers": ["META"],
                        "missing_tickers": [],
                        "covered_metric_families": ["advertising"],
                        "missing_metric_families": [],
                        "coverage_complete": True,
                        "answer_status": "complete",
                    },
                    {
                        "task_id": "task_amzn_cloud",
                        "required_tickers": ["AMZN"],
                        "covered_tickers": ["AMZN"],
                        "missing_tickers": [],
                        "covered_metric_families": ["cloud"],
                        "missing_metric_families": [],
                        "coverage_complete": True,
                        "answer_status": "complete",
                    },
                ],
                "summary": {
                    "task_count": 3,
                    "coverage_complete": True,
                    "answer_status": "complete",
                    "covered_focus_tickers": ["AMZN", "META"],
                    "missing_metric_families": [],
                    "ledger_row_count": 3,
                    "context_row_count": 3,
                },
            },
        ),
        "judgment_plan": _write_json(
            run_root / "runtime_judgment_plan.json",
            {
                "schema_version": "fixture_runtime_judgment_plan_v0.1",
                "plans": [
                    {
                        "case_id": ALT_COMPLETED_ANSWER_ID,
                        "decision_drivers": [
                            {
                                "driver_id": "jp_driver_amzn_ads",
                                "driver_claim": "AMZN advertising revenue growth is supported by SEC 10-K evidence.",
                                "supporting_metric_ids": ["fixture_amzn_advertising_revenue_2025"],
                                "supporting_evidence_ids": ["fixture_ev_amzn_ads_2025"],
                            },
                            {
                                "driver_id": "jp_driver_meta_ads",
                                "driver_claim": "META advertising scale is supported by SEC 10-K evidence.",
                                "supporting_metric_ids": ["fixture_meta_advertising_revenue_2025"],
                                "supporting_evidence_ids": ["fixture_ev_meta_ads_2025"],
                            },
                        ],
                    }
                ],
            },
        ),
        "evidence_pack": _write_json(run_root / "evidence_pack.json", {"schema_version": "fixture_evidence_pack_v0.1"}),
        "memo_answer": _write_jsonl(
            run_root / "qwen" / "agent_outputs.jsonl",
            [
                {
                    "schema_version": "fixture_agent_output_v0.1",
                    "case_id": ALT_COMPLETED_ANSWER_ID,
                    "status": "answered",
                    "answer": {
                        "summary": "Fixture AMZN/META memo summary.",
                        "decision_drivers": [
                            {
                                "driver_claim": "AMZN advertising revenue growth supports the monetization driver.",
                                "why_it_matters": "Advertising is an incremental revenue stream alongside retail and cloud.",
                                "supporting_metric_ids": ["fixture_amzn_advertising_revenue_2025"],
                                "supporting_evidence_ids": ["fixture_ev_amzn_ads_2025"],
                                "conclusion_strength": "medium",
                            },
                            {
                                "driver_claim": "META advertising revenue scale supports the platform monetization driver.",
                                "why_it_matters": "Advertising remains central to META's revenue base.",
                                "supporting_metric_ids": ["fixture_meta_advertising_revenue_2025"],
                                "supporting_evidence_ids": ["fixture_ev_meta_ads_2025"],
                                "conclusion_strength": "medium",
                            },
                        ],
                        "why_it_matters": [
                            {
                                "insight": "AMZN advertising business growth broadens monetization beyond online stores.",
                                "business_implication": "AMZN advertising growth can support margin mix if SEC-reported revenue continues to scale.",
                                "metric_ids": ["fixture_amzn_advertising_revenue_2025"],
                                "evidence_ids": ["fixture_ev_amzn_ads_2025"],
                                "confidence": "high",
                            },
                            {
                                "insight": "AWS cloud services remain a separate AMZN growth driver.",
                                "business_implication": "AWS scale affects AMZN profit mix and capital allocation.",
                                "metric_ids": ["fixture_amzn_aws_sales_2025"],
                                "evidence_ids": ["fixture_ev_amzn_aws_2025"],
                                "confidence": "high",
                            },
                            {
                                "insight": "META advertising scale remains core to the comparison.",
                                "business_implication": "META advertising revenue is the main peer readthrough for AMZN advertising.",
                                "metric_ids": ["fixture_meta_advertising_revenue_2025"],
                                "evidence_ids": ["fixture_ev_meta_ads_2025"],
                                "confidence": "high",
                            },
                        ],
                        "what_changed": [
                            {
                                "claim": "AMZN advertising revenue increased in the fixture period.",
                                "metric_ids": ["fixture_amzn_advertising_revenue_2025"],
                                "evidence_ids": ["fixture_ev_amzn_ads_2025"],
                                "confidence": "high",
                            }
                        ],
                        "key_points": [],
                        "not_found": [],
                        "limitations": [],
                    },
                }
            ],
        ),
        "claim_verification": _write_json(run_root / "claim_verification.json", {"schema_version": "fixture_claim_verification_v0.1"}),
        "deterministic_gates": _write_json(run_root / "deterministic_gates.json", {"schema_version": "fixture_gates_v0.1", "all_pass": True}),
        "rendered_answer": _write_text(run_root / "rendered_answer.md", "# Fixture AMZN META Memo\n"),
    }
    state_path = _write_state(run_root, ALT_COMPLETED_ANSWER_ID, "Fixture completed AMZN/META memo", ["AMZN", "META"], [2025], files)
    session_path = _write_session(
        session_root=session_root,
        session_id=ALT_COMPLETED_SESSION_ID,
        user_id=ALT_COMPLETED_USER_ID,
        tenant_id=COMPLETED_TENANT_ID,
        active_answer_id=ALT_COMPLETED_ANSWER_ID,
        active_query="Fixture completed AMZN/META 2025 memo",
        active_scope={"selected_tickers": ["AMZN", "META"], "selected_years": [2025], "source_policy": "SEC_ONLY_10K"},
        analysis={
            "answer_id": ALT_COMPLETED_ANSWER_ID,
            "query": "Fixture completed AMZN/META 2025 memo",
            "status": "completed",
            "run_root": str(run_root),
            "state_path": str(state_path),
            "artifact_refs": _state_artifact_refs(state_path),
            "invalidated_artifacts": [],
            "execution": {"execute": False, "returncode": 0, "elapsed_sec": 0.0},
        },
    )
    return {"run_root": run_root, "session_path": session_path, "state_path": state_path}


def _write_partial_fixture(fixture_root: Path) -> dict[str, Any]:
    run_root = fixture_root / "runs" / "partial_amzn_meta"
    session_root = fixture_root / "session_harness"
    run_root.mkdir(parents=True, exist_ok=True)
    files = {
        "query_contract": _write_json(
            run_root / "query_contract.json",
            {
                "schema_version": "fixture_query_contract_v0.1",
                "case_id": PARTIAL_ANSWER_ID,
                "task_type": "investment_memo",
                "focus_tickers": ["AMZN", "META"],
                "years": [2024, 2025],
            },
        ),
        "retrieved_context": _write_jsonl(
            run_root / "retrieved_context.jsonl",
            [
                {"object_id": "fixture_ev_amzn_ads_2025", "ticker": "AMZN", "year": 2025, "text": "AMZN ads fixture."},
                {"object_id": "fixture_ev_meta_ads_2025", "ticker": "META", "year": 2025, "text": "META ads fixture."},
            ],
        ),
        "runtime_exact_value_ledger": _write_json(
            run_root / "runtime_exact_value_ledger.json",
            {
                "schema_version": "fixture_runtime_exact_value_ledger_v0.1",
                "rows": [
                    {
                        "metric_id": "fixture_amzn_ads_2025",
                        "ticker": "AMZN",
                        "fiscal_year": 2025,
                        "metric_name": "advertising revenue",
                        "value": 56000,
                        "unit": "usd_millions",
                        "source_evidence_id": "fixture_ev_amzn_ads_2025",
                    }
                ],
            },
        ),
    }
    state_path = _write_state(run_root, PARTIAL_ANSWER_ID, "Fixture partial memo", ["AMZN", "META"], [2024, 2025], files)
    state = SecAgentState.read_json(state_path)
    state.status = "partial"
    state.write_json(state_path)
    session_path = _write_session(
        session_root=session_root,
        session_id=PARTIAL_SESSION_ID,
        user_id=PARTIAL_USER_ID,
        tenant_id=COMPLETED_TENANT_ID,
        active_answer_id=PARTIAL_ANSWER_ID,
        active_query="Fixture partial AMZN/META 2024-2025 memo",
        active_scope={"selected_tickers": ["AMZN", "META"], "selected_years": [2024, 2025], "source_policy": "SEC_ONLY_10K"},
        analysis={
            "answer_id": PARTIAL_ANSWER_ID,
            "query": "Fixture partial AMZN/META 2024-2025 memo",
            "status": "partial",
            "run_root": str(run_root),
            "state_path": str(state_path),
            "artifact_refs": _state_artifact_refs(state_path),
            "invalidated_artifacts": [],
            "execution": {"execute": False, "returncode": None, "elapsed_sec": 0.0},
        },
    )
    return {"run_root": run_root, "session_path": session_path, "state_path": state_path}


def _write_state(
    run_root: Path,
    run_id: str,
    query: str,
    tickers: list[str],
    years: list[int],
    files: dict[str, Path],
) -> Path:
    state = SecAgentState.create(
        run_id=run_id,
        user_query=query,
        output_dir=run_root,
        selected_tickers=tickers,
        selected_years=years,
        model_routes={"synthesis": {"backend": "fixture", "model": "fixture"}},
        metadata={"fixture": True},
    )
    for key in ARTIFACT_KEYS:
        path = files.get(key)
        if path:
            state.with_artifact(key, path, schema_version=f"fixture_{key}_v0.1")
    for stage_name in (
        "plan_query",
        "retrieve_context",
        "rerank_context",
        "build_runtime_ledger",
        "build_coverage_matrix",
        "build_judgment_plan",
        "synthesize_memo",
        "verify_claims",
        "run_deterministic_gates",
        "render_answer",
    ):
        outputs = _stage_outputs(stage_name)
        if outputs and all(key in files for key in outputs):
            state.mark_stage(stage_name, "completed", message="fixture completed")
    return state.write_json(run_root / "sec_agent_state.json")


def _stage_outputs(stage_name: str) -> tuple[str, ...]:
    return {
        "plan_query": ("query_contract",),
        "retrieve_context": ("retrieved_context",),
        "rerank_context": ("retrieved_context",),
        "build_runtime_ledger": ("runtime_exact_value_ledger",),
        "build_coverage_matrix": ("evidence_coverage_matrix",),
        "build_judgment_plan": ("judgment_plan",),
        "synthesize_memo": ("evidence_pack", "memo_answer"),
        "verify_claims": ("claim_verification",),
        "run_deterministic_gates": ("deterministic_gates",),
        "render_answer": ("rendered_answer",),
    }.get(stage_name, ())


def _write_session(
    *,
    session_root: Path,
    session_id: str,
    user_id: str,
    tenant_id: str,
    active_answer_id: str,
    active_query: str,
    active_scope: dict[str, Any],
    analysis: dict[str, Any],
) -> Path:
    path = session_root / session_id / "session_state.json"
    payload = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "session_id": session_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "preferences": {
            "language": "zh",
            "default_source_policy": "SEC_ONLY_10K",
            "default_years": active_scope.get("selected_years") or [],
            "preferred_output": "investment_memo",
            "risk_tone": "conservative",
        },
        "conversation_summary": "fixture session",
        "active_query": active_query,
        "active_scope": active_scope,
        "active_answer_id": active_answer_id,
        "analyses": {active_answer_id: analysis},
        "turns": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _state_artifact_refs(state_path: Path) -> dict[str, Any]:
    state = SecAgentState.read_json(state_path)
    return {key: ref.to_dict() for key, ref in state.artifacts.items()}


def _session_turn_count(session_path: Path) -> int:
    return len((json.loads(session_path.read_text(encoding="utf-8")).get("turns") or []))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _prepare_fixture_root(path: Path) -> None:
    resolved = path.resolve()
    repo = REPO_ROOT.resolve()
    _assert(str(resolved).startswith(str(repo)), f"fixture root must stay inside repo: {resolved}")
    if resolved.exists():
        _safe_rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def _safe_rmtree(path: Path) -> None:
    resolved = path.resolve()
    repo = REPO_ROOT.resolve()
    _assert(str(resolved).startswith(str(repo)), f"refusing to remove outside repo: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
