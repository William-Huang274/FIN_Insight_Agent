from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.context_manager import ContextBudget, SecAgentContextManager  # noqa: E402
from sec_agent.graph_state import ARTIFACT_KEYS, SecAgentState  # noqa: E402
from sec_agent.tool_harness import SESSION_SCHEMA_VERSION, SecAgentToolHarness  # noqa: E402


DEFAULT_EVAL_SET = REPO_ROOT / "eval_sets" / "sec_agent_context_state_replay_eval_v1.json"
DEFAULT_FIXTURE_ROOT = REPO_ROOT / "reports" / "quality" / "local_context_state_replay_fixture_runtime"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "quality" / "local_context_state_replay_v1.json"

TENANT_ID = "ctx_tenant"
USER_A = "ctx_user_a"
USER_B = "ctx_user_b"
NVDA_SESSION_ID = "ctx_session_a_nvda_2024"
NVDA_ANSWER_ID = "ctx_ans_a_nvda_2024"
AMZN_SESSION_ID = "ctx_session_a_amzn_meta_2025"
AMZN_ANSWER_ID = "ctx_ans_a_amzn_meta_2025"
PARTIAL_SESSION_ID = "ctx_session_a_partial_amzn_meta"
PARTIAL_ANSWER_ID = "ctx_ans_a_partial_amzn_meta_2024_2025"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate SEC agent ContextManager state replay behavior.")
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET))
    parser.add_argument("--fixture-root", default=str(DEFAULT_FIXTURE_ROOT))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--keep-fixtures", action="store_true", default=True)
    parser.add_argument("--clean-fixtures", dest="keep_fixtures", action="store_false")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    eval_set = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))
    fixture_root = Path(args.fixture_root).resolve()
    _prepare_fixture_root(fixture_root)
    fixtures = _write_fixture_world(fixture_root)

    budget = ContextBudget(target_controller_tokens=3000, caution_controller_tokens=6000, max_recent_turns=5, max_candidate_sessions=3)
    manager = SecAgentContextManager(
        session_root=fixture_root / "session_harness",
        context_root=fixture_root / "context_store",
        budget=budget,
    )
    manager.ingest_sessions()
    manager.set_active_session(tenant_id=TENANT_ID, user_id=USER_A, session_id=NVDA_SESSION_ID)

    harness = SecAgentToolHarness(
        session_root=fixture_root / "session_harness",
        python="__sec_agent_context_fixture_should_not_execute__",
        repo_root=REPO_ROOT,
    )
    runtime = {
        "fixture_root": fixture_root,
        "fixtures": fixtures,
        "manager": manager,
        "harness": harness,
        "budget": budget,
    }
    case_funcs: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "state_replay_reload_active_answer_001": _case_reload_active_answer,
        "state_replay_explicit_session_switch_no_leakage_001": _case_explicit_switch_no_leakage,
        "state_replay_user_boundary_denied_001": _case_user_boundary_denied,
        "state_replay_partial_resume_artifact_state_001": _case_partial_resume_artifact_state,
        "state_replay_reformat_invalidates_rendered_only_001": _case_reformat_invalidates_rendered_only,
        "state_replay_ambiguous_without_active_returns_candidates_001": _case_ambiguous_without_active_returns_candidates,
        "state_replay_compression_budget_guard_001": _case_compression_budget_guard,
    }
    case_results = []
    for case in eval_set:
        case_id = str(case.get("case_id") or "")
        func = case_funcs.get(case_id)
        if func is None:
            case_results.append({"case_id": case_id, "passed": False, "error": "case function not implemented"})
            continue
        case_results.append(_run_case(case_id, lambda func=func: func(runtime)))

    failures = [case for case in case_results if not case["passed"]]
    summary = {
        "schema_version": "sec_agent_context_state_replay_eval_result_v0.1",
        "run_id": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_context_state_replay_v1",
        "eval_set": str(Path(args.eval_set).resolve()),
        "fixture_root": str(fixture_root),
        "case_count": len(case_results),
        "passed_count": sum(1 for case in case_results if case["passed"]),
        "failed_count": len(failures),
        "all_pass": not failures,
        "failures": failures,
        "cases": case_results,
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
    "eval_set",
    "fixture_root",
    "case_count",
    "passed_count",
    "failed_count",
    "all_pass",
)


def _run_case(name: str, func: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return {"case_id": name, "passed": True, "details": func()}
    except Exception as exc:
        return {
            "case_id": name,
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _case_reload_active_answer(runtime: dict[str, Any]) -> dict[str, Any]:
    fixture_root = runtime["fixture_root"]
    reloaded = SecAgentContextManager(
        session_root=fixture_root / "session_harness",
        context_root=fixture_root / "context_store",
        budget=runtime["budget"],
    )
    snapshot = reloaded.build_controller_context(
        tenant_id=TENANT_ID,
        user_id=USER_A,
        user_message="继续刚才那个 NVDA 2024 memo，先恢复当前 active answer。",
        include_session_candidates=True,
    )
    _assert(snapshot["status"] == "ready", "reloaded active context should be ready")
    lossless = snapshot["lossless_fields"]
    _assert(lossless["session_id"] == NVDA_SESSION_ID, "active session should survive manager reload")
    _assert(lossless["active_answer_id"] == NVDA_ANSWER_ID, "active answer should survive manager reload")
    _assert("NVDA" in lossless["active_scope"]["selected_tickers"], "NVDA scope should be preserved")
    _assert(snapshot["validation_errors"] == [], "ready snapshot should validate")
    return {
        "status": snapshot["status"],
        "active_session_id": lossless["session_id"],
        "active_answer_id": lossless["active_answer_id"],
        "estimated_tokens": snapshot["compression"]["estimated_tokens"],
    }


def _case_explicit_switch_no_leakage(runtime: dict[str, Any]) -> dict[str, Any]:
    manager: SecAgentContextManager = runtime["manager"]
    manager.set_active_session(tenant_id=TENANT_ID, user_id=USER_A, session_id=AMZN_SESSION_ID)
    snapshot = manager.build_controller_context(
        tenant_id=TENANT_ID,
        user_id=USER_A,
        session_id=AMZN_SESSION_ID,
        user_message="切到 AMZN/META 2025 session，不要继承 NVDA。",
    )
    active = snapshot["active_session"]
    active_text = json.dumps(active, ensure_ascii=False)
    _assert(snapshot["status"] == "ready", "explicit switch should resolve")
    _assert(active["session_id"] == AMZN_SESSION_ID, "active session should be AMZN/META")
    _assert(sorted(active["active_scope"]["selected_tickers"]) == ["AMZN", "META"], "active scope should be AMZN/META only")
    _assert(snapshot["session_candidates"] == [], "explicit switch should not expose candidates by default")
    _assert(NVDA_ANSWER_ID not in active_text and "NVDA" not in active_text, "previous NVDA active state should not leak")
    return {
        "active_session_id": active["session_id"],
        "active_tickers": active["active_scope"]["selected_tickers"],
        "candidate_count": len(snapshot["session_candidates"]),
    }


def _case_user_boundary_denied(runtime: dict[str, Any]) -> dict[str, Any]:
    manager: SecAgentContextManager = runtime["manager"]
    snapshot = manager.build_controller_context(
        tenant_id=TENANT_ID,
        user_id=USER_B,
        session_id=NVDA_SESSION_ID,
        user_message="我想看用户 A 的 NVDA session。",
    )
    _assert(snapshot["status"] == "access_denied", "cross-user access should be denied")
    _assert(snapshot["active_session"] == {}, "denied snapshot must not expose active session")
    return {"status": snapshot["status"], "reason": snapshot["reason"]}


def _case_partial_resume_artifact_state(runtime: dict[str, Any]) -> dict[str, Any]:
    manager: SecAgentContextManager = runtime["manager"]
    manager.set_active_session(tenant_id=TENANT_ID, user_id=USER_A, session_id=PARTIAL_SESSION_ID)
    before = manager.build_controller_context(
        tenant_id=TENANT_ID,
        user_id=USER_A,
        session_id=PARTIAL_SESSION_ID,
        user_message="继续刚才没跑完的 AMZN/META memo。",
    )
    before_artifacts = before["lossless_fields"]["artifact_state"]
    before_resume = before["lossless_fields"]["resume"]
    _assert(before_resume["next_ready_node"] == "build_coverage_matrix", "partial run should resume at coverage")
    _assert("retrieved_context" in before_artifacts["complete_artifacts"], "retrieval should be complete before resume")
    _assert("runtime_exact_value_ledger" in before_artifacts["complete_artifacts"], "ledger should be complete before resume")
    _assert("evidence_coverage_matrix" in before_artifacts["missing_artifacts"], "coverage should be missing before resume")

    _complete_partial_fixture(runtime["fixtures"]["partial"])
    reloaded = SecAgentContextManager(
        session_root=runtime["fixture_root"] / "session_harness",
        context_root=runtime["fixture_root"] / "context_store",
        budget=runtime["budget"],
    )
    after = reloaded.build_controller_context(
        tenant_id=TENANT_ID,
        user_id=USER_A,
        session_id=PARTIAL_SESSION_ID,
        user_message="恢复后检查 artifacts。",
    )
    after_artifacts = after["lossless_fields"]["artifact_state"]
    after_resume = after["lossless_fields"]["resume"]
    _assert(after_resume["next_ready_node"] is None, "completed resumed state should have no next_ready_node")
    _assert(after_artifacts["missing_artifacts"] == [], "completed resumed state should have no missing artifacts")
    return {
        "before_next_ready_node": before_resume["next_ready_node"],
        "after_next_ready_node": after_resume["next_ready_node"],
        "after_complete_count": len(after_artifacts["complete_artifacts"]),
    }


def _case_reformat_invalidates_rendered_only(runtime: dict[str, Any]) -> dict[str, Any]:
    manager: SecAgentContextManager = runtime["manager"]
    harness: SecAgentToolHarness = runtime["harness"]
    manager.set_active_session(tenant_id=TENANT_ID, user_id=USER_A, session_id=AMZN_SESSION_ID)
    reformat_result = harness.dispatch(
        "reformat_answer",
        {
            "session_id": AMZN_SESSION_ID,
            "answer_id": AMZN_ANSWER_ID,
            "format": "pm_5_bullets",
            "preserve_citations": True,
            "execute": False,
        },
    ).to_dict()
    manager.apply_tool_result(tool_result=reformat_result)
    snapshot = manager.build_controller_context(
        tenant_id=TENANT_ID,
        user_id=USER_A,
        session_id=AMZN_SESSION_ID,
        user_message="reformat 后检查 artifact 状态。",
    )
    artifact_state = snapshot["lossless_fields"]["artifact_state"]
    _assert(artifact_state["invalidated_artifacts"] == ["rendered_answer"], "only rendered_answer should be invalidated")
    for key in ("retrieved_context", "runtime_exact_value_ledger", "evidence_coverage_matrix", "judgment_plan", "memo_answer"):
        _assert(artifact_state["by_key"][key]["status"] == "complete", f"{key} should remain complete")

    evidence_result = harness.dispatch(
        "explain_evidence",
        {
            "session_id": AMZN_SESSION_ID,
            "answer_id": AMZN_ANSWER_ID,
            "claim_reference": "解释 AMZN 广告业务增长那条证据。",
        },
    ).to_dict()
    payload = evidence_result["payload"]
    _assert(evidence_result["status"] == "completed", "post-reformat evidence explanation should complete")
    _assert(payload["rerun_required"] is False, "evidence explanation should not request rerun")
    _assert("ctx_amzn_advertising_revenue_2025" in payload["metric_ids"], "AMZN ads metric id should resolve")
    _assert("ctx_ev_amzn_ads_2025" in payload["evidence_ids"], "AMZN ads evidence id should resolve")
    manager.apply_tool_result(tool_result=evidence_result)
    return {
        "invalidated_artifacts": artifact_state["invalidated_artifacts"],
        "metric_ids": payload["metric_ids"],
        "evidence_ids": payload["evidence_ids"],
    }


def _case_ambiguous_without_active_returns_candidates(runtime: dict[str, Any]) -> dict[str, Any]:
    manager: SecAgentContextManager = runtime["manager"]
    manager.clear_active_session(tenant_id=TENANT_ID, user_id=USER_A)
    snapshot = manager.build_controller_context(
        tenant_id=TENANT_ID,
        user_id=USER_A,
        user_message="继续刚才那个 memo。",
    )
    _assert(snapshot["status"] == "clarification_required", "ambiguous no-active context should require clarification")
    _assert(snapshot["lossless_fields"]["active_answer_id"] == "", "ambiguous no-active context must not guess active answer")
    _assert(1 < len(snapshot["session_candidates"]) <= runtime["budget"].max_candidate_sessions, "candidate sessions should be bounded")
    return {
        "status": snapshot["status"],
        "candidate_count": len(snapshot["session_candidates"]),
        "candidate_session_ids": [item["session_id"] for item in snapshot["session_candidates"]],
    }


def _case_compression_budget_guard(runtime: dict[str, Any]) -> dict[str, Any]:
    session_path = runtime["fixture_root"] / "session_harness" / NVDA_SESSION_ID / "session_state.json"
    _append_dummy_turns(session_path, count=8)
    manager: SecAgentContextManager = runtime["manager"]
    manager.set_active_session(tenant_id=TENANT_ID, user_id=USER_A, session_id=NVDA_SESSION_ID)
    snapshot = manager.build_controller_context(
        tenant_id=TENANT_ID,
        user_id=USER_A,
        session_id=NVDA_SESSION_ID,
        user_message="继续检查 NVDA 证据覆盖。",
        include_session_candidates=True,
    )
    compression = snapshot["compression"]
    _assert(snapshot["validation_errors"] == [], "ready snapshot should validate")
    _assert(compression["estimated_tokens"] <= runtime["budget"].target_controller_tokens, "snapshot should stay within target budget")
    _assert(compression["recent_turn_count"] <= runtime["budget"].max_recent_turns, "recent turns should be bounded")
    _assert(compression["candidate_session_count"] <= runtime["budget"].max_candidate_sessions, "candidate sessions should be bounded")
    _assert(compression["attention_risk"] == "low", "bounded context should have low attention risk")
    return {
        "estimated_tokens": compression["estimated_tokens"],
        "recent_turn_count": compression["recent_turn_count"],
        "candidate_session_count": compression["candidate_session_count"],
        "attention_risk": compression["attention_risk"],
    }


def _write_fixture_world(fixture_root: Path) -> dict[str, Any]:
    session_root = fixture_root / "session_harness"
    nvda = _write_completed_fixture(
        fixture_root=fixture_root,
        run_name="completed_nvda_2024",
        session_id=NVDA_SESSION_ID,
        user_id=USER_A,
        tenant_id=TENANT_ID,
        answer_id=NVDA_ANSWER_ID,
        query="Fixture completed NVDA 2024 SEC-only memo",
        tickers=["NVDA"],
        years=[2024],
        metrics=[
            {
                "metric_id": "ctx_nvda_data_center_revenue_2024",
                "evidence_id": "ctx_ev_nvda_data_center_2024",
                "ticker": "NVDA",
                "year": 2024,
                "metric_name": "data center revenue",
                "value": 47500,
                "unit": "usd_millions",
                "claim": "NVDA data center growth supports the AI infrastructure thesis.",
            },
            {
                "metric_id": "ctx_nvda_gross_margin_2024",
                "evidence_id": "ctx_ev_nvda_margin_2024",
                "ticker": "NVDA",
                "year": 2024,
                "metric_name": "gross margin",
                "value": 73.8,
                "unit": "percent",
                "claim": "NVDA gross margin improvement supports profitability quality.",
            },
        ],
    )
    amzn = _write_completed_fixture(
        fixture_root=fixture_root,
        run_name="completed_amzn_meta_2025",
        session_id=AMZN_SESSION_ID,
        user_id=USER_A,
        tenant_id=TENANT_ID,
        answer_id=AMZN_ANSWER_ID,
        query="Fixture completed AMZN/META 2025 SEC-only memo",
        tickers=["AMZN", "META"],
        years=[2025],
        metrics=[
            {
                "metric_id": "ctx_amzn_advertising_revenue_2025",
                "evidence_id": "ctx_ev_amzn_ads_2025",
                "ticker": "AMZN",
                "year": 2025,
                "metric_name": "advertising services revenue",
                "value": 56000,
                "unit": "usd_millions",
                "claim": "AMZN advertising business growth broadens monetization beyond retail.",
            },
            {
                "metric_id": "ctx_meta_advertising_revenue_2025",
                "evidence_id": "ctx_ev_meta_ads_2025",
                "ticker": "META",
                "year": 2025,
                "metric_name": "advertising revenue",
                "value": 164000,
                "unit": "usd_millions",
                "claim": "META advertising revenue scale is the core peer readthrough.",
            },
        ],
    )
    partial = _write_partial_fixture(fixture_root=fixture_root, session_root=session_root)
    return {"nvda": nvda, "amzn": amzn, "partial": partial}


def _write_completed_fixture(
    *,
    fixture_root: Path,
    run_name: str,
    session_id: str,
    user_id: str,
    tenant_id: str,
    answer_id: str,
    query: str,
    tickers: list[str],
    years: list[int],
    metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    run_root = fixture_root / "runs" / run_name
    session_root = fixture_root / "session_harness"
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "qwen").mkdir(parents=True, exist_ok=True)
    files = _write_common_completed_artifacts(run_root=run_root, answer_id=answer_id, tickers=tickers, years=years, metrics=metrics)
    state_path = _write_state(run_root, answer_id, query, tickers, years, files)
    session_path = _write_session(
        session_root=session_root,
        session_id=session_id,
        user_id=user_id,
        tenant_id=tenant_id,
        active_answer_id=answer_id,
        active_query=query,
        active_scope={"selected_tickers": tickers, "selected_years": years, "source_policy": "SEC_ONLY_10K"},
        analysis={
            "answer_id": answer_id,
            "query": query,
            "status": "completed",
            "run_root": str(run_root),
            "state_path": str(state_path),
            "artifact_refs": _state_artifact_refs(state_path),
            "invalidated_artifacts": [],
            "execution": {"execute": False, "returncode": 0, "elapsed_sec": 0.0},
        },
    )
    return {"run_root": run_root, "session_path": session_path, "state_path": state_path, "answer_id": answer_id}


def _write_partial_fixture(*, fixture_root: Path, session_root: Path) -> dict[str, Any]:
    run_root = fixture_root / "runs" / "partial_amzn_meta_2024_2025"
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
                {"object_id": "ctx_ev_partial_amzn_ads_2025", "ticker": "AMZN", "year": 2025, "text": "AMZN ads partial fixture."},
                {"object_id": "ctx_ev_partial_meta_ads_2025", "ticker": "META", "year": 2025, "text": "META ads partial fixture."},
            ],
        ),
        "runtime_exact_value_ledger": _write_json(
            run_root / "runtime_exact_value_ledger.json",
            {
                "schema_version": "fixture_runtime_exact_value_ledger_v0.1",
                "rows": [
                    {
                        "metric_id": "ctx_partial_amzn_ads_2025",
                        "ticker": "AMZN",
                        "fiscal_year": 2025,
                        "metric_name": "advertising revenue",
                        "value": 56000,
                        "unit": "usd_millions",
                        "source_evidence_id": "ctx_ev_partial_amzn_ads_2025",
                    }
                ],
            },
        ),
    }
    state_path = _write_state(
        run_root,
        PARTIAL_ANSWER_ID,
        "Fixture partial AMZN/META 2024-2025 memo",
        ["AMZN", "META"],
        [2024, 2025],
        files,
    )
    state = SecAgentState.read_json(state_path)
    state.status = "partial"
    state.write_json(state_path)
    session_path = _write_session(
        session_root=session_root,
        session_id=PARTIAL_SESSION_ID,
        user_id=USER_A,
        tenant_id=TENANT_ID,
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
    return {"run_root": run_root, "session_path": session_path, "state_path": state_path, "answer_id": PARTIAL_ANSWER_ID}


def _complete_partial_fixture(fixture: dict[str, Any]) -> None:
    run_root = Path(fixture["run_root"])
    files = {
        "evidence_coverage_matrix": _write_json(
            run_root / "runtime_evidence_coverage_matrix.json",
            {
                "schema_version": "sec_agent_evidence_coverage_matrix_v0.1",
                "case_id": PARTIAL_ANSWER_ID,
                "tasks": [
                    {
                        "task_id": "task_partial_amzn_ads",
                        "required_tickers": ["AMZN"],
                        "covered_tickers": ["AMZN"],
                        "missing_tickers": [],
                        "covered_metric_families": ["advertising"],
                        "missing_metric_families": [],
                        "coverage_complete": True,
                        "answer_status": "complete",
                    }
                ],
                "summary": {
                    "task_count": 1,
                    "coverage_complete": True,
                    "answer_status": "complete",
                    "covered_focus_tickers": ["AMZN", "META"],
                    "missing_metric_families": [],
                    "ledger_row_count": 1,
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
                        "case_id": PARTIAL_ANSWER_ID,
                        "decision_drivers": [
                            {
                                "driver_id": "ctx_partial_driver_amzn_ads",
                                "driver_claim": "AMZN advertising revenue growth is supported by SEC 10-K evidence.",
                                "supporting_metric_ids": ["ctx_partial_amzn_ads_2025"],
                                "supporting_evidence_ids": ["ctx_ev_partial_amzn_ads_2025"],
                            }
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
                    "case_id": PARTIAL_ANSWER_ID,
                    "status": "answered",
                    "answer": {
                        "summary": "Completed partial fixture memo.",
                        "decision_drivers": [
                            {
                                "driver_claim": "AMZN advertising revenue growth supports the monetization driver.",
                                "supporting_metric_ids": ["ctx_partial_amzn_ads_2025"],
                                "supporting_evidence_ids": ["ctx_ev_partial_amzn_ads_2025"],
                            }
                        ],
                        "why_it_matters": [],
                        "what_changed": [],
                    },
                }
            ],
        ),
        "claim_verification": _write_json(run_root / "claim_verification.json", {"schema_version": "fixture_claim_verification_v0.1"}),
        "deterministic_gates": _write_json(run_root / "deterministic_gates.json", {"schema_version": "fixture_gates_v0.1", "all_pass": True}),
        "rendered_answer": _write_text(run_root / "rendered_answer.md", "# Completed Partial Fixture\n"),
    }
    state_path = Path(fixture["state_path"])
    state = SecAgentState.read_json(state_path)
    for key, path in files.items():
        state.with_artifact(key, path, schema_version=f"fixture_{key}_v0.1")
    for stage in ("build_coverage_matrix", "build_judgment_plan", "synthesize_memo", "verify_claims", "run_deterministic_gates", "render_answer"):
        state.mark_stage(stage, "completed", message="fixture completed after resume")
    state.status = "completed"
    state.write_json(state_path)

    session_path = Path(fixture["session_path"])
    session = _read_json(session_path)
    analysis = session["analyses"][PARTIAL_ANSWER_ID]
    analysis["status"] = "completed"
    analysis["artifact_refs"] = _state_artifact_refs(state_path)
    analysis["execution"] = {"execute": True, "returncode": 0, "elapsed_sec": 0.0}
    session["updated_at"] = _utc_now()
    session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_common_completed_artifacts(
    *,
    run_root: Path,
    answer_id: str,
    tickers: list[str],
    years: list[int],
    metrics: list[dict[str, Any]],
) -> dict[str, Path]:
    files = {
        "query_contract": _write_json(
            run_root / "query_contract.json",
            {
                "schema_version": "fixture_query_contract_v0.1",
                "case_id": answer_id,
                "task_type": "investment_memo",
                "focus_tickers": tickers,
                "years": years,
            },
        ),
        "retrieved_context": _write_jsonl(
            run_root / "retrieved_context.jsonl",
            [
                {
                    "object_id": item["evidence_id"],
                    "ticker": item["ticker"],
                    "year": item["year"],
                    "section": "Item 7",
                    "text": f"{item['claim']} fixture snippet.",
                }
                for item in metrics
            ],
        ),
        "runtime_exact_value_ledger": _write_json(
            run_root / "runtime_exact_value_ledger.json",
            {
                "schema_version": "fixture_runtime_exact_value_ledger_v0.1",
                "rows": [
                    {
                        "metric_id": item["metric_id"],
                        "ticker": item["ticker"],
                        "fiscal_year": item["year"],
                        "metric_name": item["metric_name"],
                        "value": item["value"],
                        "unit": item["unit"],
                        "source_evidence_id": item["evidence_id"],
                        "object_id": item["evidence_id"],
                        "preview": item["claim"],
                    }
                    for item in metrics
                ],
            },
        ),
        "evidence_coverage_matrix": _write_json(
            run_root / "runtime_evidence_coverage_matrix.json",
            {
                "schema_version": "sec_agent_evidence_coverage_matrix_v0.1",
                "case_id": answer_id,
                "tasks": [
                    {
                        "task_id": f"task_{item['metric_id']}",
                        "required_tickers": [item["ticker"]],
                        "covered_tickers": [item["ticker"]],
                        "missing_tickers": [],
                        "covered_metric_families": [_metric_family(item["metric_name"])],
                        "missing_metric_families": [],
                        "coverage_complete": True,
                        "answer_status": "complete",
                    }
                    for item in metrics
                ],
                "summary": {
                    "task_count": len(metrics),
                    "coverage_complete": True,
                    "answer_status": "complete",
                    "covered_focus_tickers": sorted(set(tickers)),
                    "missing_metric_families": [],
                    "ledger_row_count": len(metrics),
                    "context_row_count": len(metrics),
                },
            },
        ),
        "judgment_plan": _write_json(
            run_root / "runtime_judgment_plan.json",
            {
                "schema_version": "fixture_runtime_judgment_plan_v0.1",
                "plans": [
                    {
                        "case_id": answer_id,
                        "decision_drivers": [
                            {
                                "driver_id": f"driver_{item['metric_id']}",
                                "driver_claim": item["claim"],
                                "supporting_metric_ids": [item["metric_id"]],
                                "supporting_evidence_ids": [item["evidence_id"]],
                            }
                            for item in metrics
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
                    "case_id": answer_id,
                    "status": "answered",
                    "answer": {
                        "summary": "Fixture memo summary.",
                        "decision_drivers": [
                            {
                                "driver_claim": item["claim"],
                                "supporting_metric_ids": [item["metric_id"]],
                                "supporting_evidence_ids": [item["evidence_id"]],
                                "conclusion_strength": "medium",
                            }
                            for item in metrics
                        ],
                        "why_it_matters": [
                            {
                                "insight": item["claim"],
                                "business_implication": item["claim"],
                                "metric_ids": [item["metric_id"]],
                                "evidence_ids": [item["evidence_id"]],
                                "confidence": "high",
                            }
                            for item in metrics
                        ],
                        "what_changed": [
                            {
                                "claim": metrics[0]["claim"],
                                "metric_ids": [metrics[0]["metric_id"]],
                                "evidence_ids": [metrics[0]["evidence_id"]],
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
    return files


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


def _append_dummy_turns(session_path: Path, *, count: int) -> None:
    session = _read_json(session_path)
    turns = session.setdefault("turns", [])
    for index in range(count):
        turns.append(
            {
                "turn_id": f"dummy_{index + 1:03d}",
                "tool_name": "inspect_coverage",
                "arguments": {"answer_id": session.get("active_answer_id") or ""},
                "created_at": _utc_now(),
                "status": "completed",
            }
        )
    session["updated_at"] = _utc_now()
    session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _state_artifact_refs(state_path: Path) -> dict[str, Any]:
    state = SecAgentState.read_json(state_path)
    return {key: ref.to_dict() for key, ref in state.artifacts.items()}


def _metric_family(metric_name: str) -> str:
    text = str(metric_name or "").lower()
    if "advertising" in text:
        return "advertising"
    if "gross margin" in text or "margin" in text:
        return "gross_margin"
    if "data center" in text:
        return "data_center"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "metric"


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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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
