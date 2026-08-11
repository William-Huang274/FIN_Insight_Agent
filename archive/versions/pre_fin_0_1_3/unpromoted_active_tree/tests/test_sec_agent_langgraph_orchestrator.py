from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import time
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.langgraph_orchestrator import (  # noqa: E402
    build_native_state_smoke_graph,
    hydrate_native_state_from_checkpoint_artifact,
    inspect_node_checkpoint_artifact,
    make_native_smoke_state,
    native_node_order,
    wrap_checkpoint_saver_for_sec_agent_state,
)
from sec_agent.query_contract import validate_query_contract  # noqa: E402


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    return path


def _native_resume_base_state(tmp_path: Path) -> dict:
    query_contract = {
        "task_type": "open_analysis",
        "search_scope_tickers": ["AMD"],
        "focus_tickers": ["AMD"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["capex"],
        "decomposed_tasks": [
            {
                "task_id": "amd_capex",
                "question_zh": "分析 AMD 资本开支。",
                "priority": "primary",
                "required_tickers": ["AMD"],
                "required_metric_families": ["capex"],
            }
        ],
    }
    context_rows = [{"evidence_id": "AMD_SEC", "ticker": "AMD", "text": "AMD capex context"}]
    ledger_rows = [{"metric_id": "AMD_CAPEX", "ticker": "AMD", "fiscal_year": 2026, "metric_family": "capex", "value": 1}]
    coverage_matrix = {"summary": {"coverage_complete": True, "primary_task_support_complete": True}}
    judgment_plan = {"drivers": [{"rank": 1, "claim": "AMD capex is supported."}]}
    case_path = _write_jsonl(
        tmp_path / "case.jsonl",
        [{"case_id": "unit_case", "prompt": "分析 AMD 资本开支", "companies": ["AMD"], "years": [2026], "query_contract": query_contract}],
    )
    context_path = _write_jsonl(tmp_path / "trace" / "trace_logs.jsonl", [{"stage": "retrieval", "context_rows": context_rows}])
    ledger_path = _write_json(tmp_path / "runtime_exact_value_ledger.json", {"rows": ledger_rows})
    coverage_path = _write_json(tmp_path / "runtime_evidence_coverage_matrix.json", coverage_matrix)
    judgment_path = _write_json(tmp_path / "runtime_judgment_plan.json", judgment_plan)
    state = make_native_smoke_state(user_query="分析 AMD 资本开支", output_dir=tmp_path, query_contract=query_contract)
    state.update(
        {
            "context_rows": context_rows,
            "runtime_ledger_rows": ledger_rows,
            "coverage_matrix": coverage_matrix,
            "judgment_plan": judgment_plan,
            "artifact_refs": {
                "case": str(case_path),
                "retrieved_context": str(context_path),
                "runtime_exact_value_ledger": str(ledger_path),
                "evidence_coverage_matrix": str(coverage_path),
                "judgment_plan": str(judgment_path),
            },
        }
    )
    return state


def test_all_scope_keeps_full_universe_for_broad_ai_prompt() -> None:
    interactive = _load_interactive_module()
    available = {
        ("NVDA", 2026),
        ("AMD", 2026),
        ("JPM", 2026),
        ("XOM", 2026),
    }

    tickers = interactive._resolve_tickers("ALL", "比较这些公司在 AI 相关业务上的表现", available)

    assert tickers == ["AMD", "JPM", "NVDA", "XOM"]


def test_query_contract_marks_representative_focus_without_shrinking_search_scope() -> None:
    inventory = {
        "inventory_digest": "scope-test",
        "companies": [
            {
                "ticker": ticker,
                "category": "mixed",
                "filings": [{"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"}],
            }
            for ticker in ["NVDA", "AMD", "JPM", "XOM"]
        ],
        "categories": [{"category": "mixed", "tickers": ["NVDA", "AMD", "JPM", "XOM"]}],
    }
    contract = {
        "task_type": "ai_industry_financial_trend",
        "search_scope_tickers": ["NVDA", "AMD", "JPM", "XOM"],
        "focus_tickers": ["NVDA", "AMD"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["revenue"],
        "decomposed_tasks": [
            {
                "task_id": "ai_rep",
                "question_zh": "比较 AI 相关代表公司的财务表现。",
                "priority": "primary",
                "required_tickers": ["NVDA", "AMD"],
                "required_metric_families": ["revenue"],
            },
            {
                "task_id": "scope_boundary",
                "question_zh": "记录未进入代表样本的公司范围边界。",
                "priority": "supporting",
                "required_tickers": ["JPM", "XOM"],
                "required_metric_families": ["revenue"],
            },
        ],
    }

    result = validate_query_contract(
        contract,
        selected_tickers=["NVDA", "AMD", "JPM", "XOM"],
        selected_years=[2026],
        project_inventory=inventory,
    )
    clean = result["contract"]

    assert result["report"]["status"] == "pass"
    assert clean["search_scope_tickers"] == ["NVDA", "AMD", "JPM", "XOM"]
    assert clean["focus_tickers"] == ["NVDA", "AMD"]
    assert clean["scope_mode"] == "sector_representative"
    assert clean["scope"]["universe_count"] == 4
    assert clean["scope"]["focus_count"] == 2
    assert clean["scope"]["representative_tickers"] == ["NVDA", "AMD"]


def test_native_graph_smoke_runs_business_node_skeleton(tmp_path: Path) -> None:
    graph = build_native_state_smoke_graph()
    initial = make_native_smoke_state(
        user_query="比较 NVDA 和 AMD",
        output_dir=tmp_path,
        query_contract={
            "task_type": "company_comparison",
            "search_scope_tickers": ["NVDA", "AMD"],
            "focus_tickers": ["NVDA", "AMD"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["revenue"],
            "decomposed_tasks": [
                {
                    "task_id": "compare_revenue",
                    "question_zh": "比较收入趋势。",
                    "priority": "primary",
                    "required_tickers": ["NVDA", "AMD"],
                    "required_metric_families": ["revenue"],
                }
            ],
        },
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-native-graph"}})

    assert result["status"] == "completed"
    assert [row["node"] for row in result["node_trace"]] == list(native_node_order())
    assert [row["node"] for row in result["node_checkpoints"]] == list(native_node_order())
    assert result["node_checkpoints"][0]["schema_version"] == "sec_agent_langgraph_node_checkpoint_v0.1"
    assert result["node_checkpoints"][-1]["state_summary"]["status"] == "completed"
    assert (result["retrieval_plan"].get("retrieval_plan_validation") or {})["status"] == "pass"
    summary_path = tmp_path / "langgraph_native_summary.json"
    checkpoint_path = tmp_path / "langgraph_node_checkpoints.json"
    assert summary_path.exists()
    assert checkpoint_path.exists()
    saved = json.loads(summary_path.read_text(encoding="utf-8"))
    checkpoint_artifact = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert [row["node"] for row in saved["node_trace"]] == list(native_node_order())
    assert [row["node"] for row in saved["node_checkpoints"]] == list(native_node_order())
    assert saved["artifact_refs"]["node_checkpoints"] == str(checkpoint_path.resolve())
    assert checkpoint_artifact["schema_version"] == "sec_agent_langgraph_node_checkpoint_artifact_v0.1"
    assert checkpoint_artifact["checkpoint_count"] == len(native_node_order())
    assert checkpoint_artifact["latest_completed_node"] == "persist_session_state"
    assert checkpoint_artifact["recoverable_state_summary"]["status"] == "completed"
    assert checkpoint_artifact["payload_policy"]["large_payloads"] == "external_artifacts"
    assert checkpoint_artifact["artifact_refs"]["node_checkpoints"]["exists"] is True
    assert checkpoint_artifact["artifact_refs"]["node_checkpoints"]["self_referential"] is True

    inspection = inspect_node_checkpoint_artifact(checkpoint_path)
    assert inspection["schema_version"] == "sec_agent_langgraph_checkpoint_resume_inspection_v0.1"
    assert inspection["latest_completed_node"] == "persist_session_state"
    assert inspection["next_recoverable_node"] == ""
    assert inspection["resume_supported"] is False
    assert inspection["blocked_reasons"] == ["no_next_node"]


def test_native_node_trace_records_elapsed_ms(tmp_path: Path) -> None:
    def retrieve_context(_state):
        time.sleep(0.02)
        return {"context_rows": [{"evidence_id": "E1", "ticker": "NVDA"}]}

    graph = build_native_state_smoke_graph(retrieve_context=retrieve_context)
    result = graph.invoke(
        make_native_smoke_state(user_query="分析 NVDA", output_dir=tmp_path),
        config={"configurable": {"thread_id": "unit-native-node-timing"}},
    )

    trace_row = [row for row in result["node_trace"] if row["node"] == "execute_retrieval_routes"][0]
    checkpoint_row = [row for row in result["node_checkpoints"] if row["node"] == "execute_retrieval_routes"][0]
    assert trace_row["elapsed_ms"] >= 1
    assert checkpoint_row["elapsed_ms"] >= 1
    assert trace_row["started_at"]
    assert checkpoint_row["started_at"]
    saved = json.loads((tmp_path / "langgraph_native_summary.json").read_text(encoding="utf-8"))
    saved_row = [row for row in saved["node_trace"] if row["node"] == "execute_retrieval_routes"][0]
    assert saved_row["elapsed_ms"] >= 1


def test_native_graph_accepts_sqlite_checkpointer(tmp_path: Path) -> None:
    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = tmp_path / "langgraph_checkpoints.sqlite"
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        saver.setup()
        graph = build_native_state_smoke_graph(checkpointer=wrap_checkpoint_saver_for_sec_agent_state(saver))
        result = graph.invoke(
            make_native_smoke_state(user_query="sqlite checkpoint smoke", output_dir=tmp_path / "run"),
            config={"configurable": {"thread_id": "unit-native-sqlite-checkpoint"}},
        )

    assert result["status"] == "completed"
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("select name from sqlite_master where type='table'").fetchall()
        }
    assert "checkpoints" in tables


def test_native_sqlite_checkpointer_externalizes_large_payloads(tmp_path: Path) -> None:
    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = tmp_path / "langgraph_checkpoints.sqlite"
    context_path = tmp_path / "run" / "retrieved_context.jsonl"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text('{"evidence_id":"E1"}\n', encoding="utf-8")

    def retrieve_context(_state):
        return {
            "context_rows": [
                {"evidence_id": f"E{i}", "text": "x" * 1000, "ticker": "NVDA"}
                for i in range(25)
            ],
            "artifact_refs": {"retrieved_context": str(context_path)},
        }

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        saver.setup()
        graph = build_native_state_smoke_graph(
            checkpointer=wrap_checkpoint_saver_for_sec_agent_state(saver),
            retrieve_context=retrieve_context,
        )
        result = graph.invoke(
            make_native_smoke_state(user_query="sqlite large payload smoke", output_dir=tmp_path / "run"),
            config={"configurable": {"thread_id": "unit-native-sqlite-slim"}},
        )

    assert len(result["context_rows"]) == 25
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        checkpoint = next(saver.list({"configurable": {"thread_id": "unit-native-sqlite-slim"}}, limit=1)).checkpoint
    context_checkpoint = checkpoint["channel_values"]["context_rows"]
    assert context_checkpoint["__sec_agent_checkpoint_payload__"] == "externalized_summary"
    assert context_checkpoint["row_count"] == 25
    assert "digest" in context_checkpoint


def test_native_checkpoint_hydrates_retrieval_boundary(tmp_path: Path) -> None:
    context_path = tmp_path / "run" / "trace" / "trace_logs.jsonl"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(
        "\n".join(json.dumps({"evidence_id": f"E{i}", "ticker": "NVDA"}) for i in range(3)) + "\n",
        encoding="utf-8",
    )

    def retrieve_context(_state):
        return {
            "context_rows": [
                {"evidence_id": f"E{i}", "ticker": "NVDA", "text": "evidence"}
                for i in range(3)
            ],
            "artifact_refs": {"retrieved_context": str(context_path)},
        }

    graph = build_native_state_smoke_graph(retrieve_context=retrieve_context)
    result = graph.invoke(
        make_native_smoke_state(
            user_query="hydrate retrieval boundary",
            output_dir=tmp_path / "run",
            query_contract={
                "task_type": "company_comparison",
                "search_scope_tickers": ["NVDA"],
                "focus_tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
            },
        ),
        config={"configurable": {"thread_id": "unit-native-hydrate-retrieval"}},
    )
    checkpoint_path = tmp_path / "run" / "langgraph_node_checkpoints.json"
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoints = payload["node_checkpoints"]
    index = [row["node"] for row in checkpoints].index("execute_retrieval_routes")
    partial = dict(payload)
    partial["status"] = "running"
    partial["node_checkpoints"] = checkpoints[: index + 1]
    partial["checkpoint_count"] = len(partial["node_checkpoints"])
    partial["latest_completed_node"] = "execute_retrieval_routes"
    partial["latest_checkpoint_id"] = checkpoints[index]["checkpoint_id"]
    partial["recoverable_state_summary"] = checkpoints[index]["state_summary"]
    partial_path = tmp_path / "run" / "partial_retrieval_checkpoint.json"
    partial_path.write_text(json.dumps(partial, ensure_ascii=False, indent=2), encoding="utf-8")

    hydrated = hydrate_native_state_from_checkpoint_artifact(partial_path)

    assert result["context_rows"][0]["evidence_id"] == "E0"
    assert hydrated["resume_supported"] is True
    assert hydrated["next_recoverable_node"] == "attach_market_snapshot"
    assert hydrated["state_summary"]["context_row_count"] == 3
    assert hydrated["state"]["context_rows"][0]["evidence_id"] == "E0"

    resume_graph = build_native_state_smoke_graph(entry_node=hydrated["next_recoverable_node"])
    resumed = resume_graph.invoke(
        hydrated["state"],
        config={"configurable": {"thread_id": "unit-native-hydrate-retrieval-resume"}},
    )
    assert resumed["status"] == "completed"
    assert resumed["node_trace"][index + 1]["node"] == "attach_market_snapshot"


def test_native_stop_after_node_writes_real_partial_checkpoint(tmp_path: Path) -> None:
    context_path = tmp_path / "run" / "trace" / "trace_logs.jsonl"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_rows = [{"evidence_id": f"E{i}", "ticker": "NVDA", "text": "evidence"} for i in range(4)]
    context_path.write_text(
        json.dumps({"stage": "retrieval", "context_rows": context_rows}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    def retrieve_context(_state):
        return {
            "context_rows": context_rows,
            "artifact_refs": {"retrieved_context": str(context_path)},
        }

    graph = build_native_state_smoke_graph(
        retrieve_context=retrieve_context,
        stop_after_node="execute_retrieval_routes",
    )
    result = graph.invoke(
        make_native_smoke_state(user_query="stop after retrieval", output_dir=tmp_path / "run"),
        config={"configurable": {"thread_id": "unit-native-stop-after-node"}},
    )

    checkpoint_path = tmp_path / "run" / "langgraph_node_checkpoints.json"
    assert result["status"] == "stopped_after_node"
    assert result["native_stop_after_node"] == "execute_retrieval_routes"
    assert [row["node"] for row in result["node_trace"]][-1] == "execute_retrieval_routes"
    assert checkpoint_path.exists()

    inspection = inspect_node_checkpoint_artifact(checkpoint_path)
    assert inspection["resume_supported"] is True
    assert inspection["latest_completed_node"] == "execute_retrieval_routes"
    assert inspection["next_recoverable_node"] == "attach_market_snapshot"

    hydrated = hydrate_native_state_from_checkpoint_artifact(checkpoint_path)
    assert hydrated["state_summary"]["context_row_count"] == 4
    resume_graph = build_native_state_smoke_graph(entry_node=hydrated["next_recoverable_node"])
    resumed = resume_graph.invoke(
        hydrated["state"],
        config={"configurable": {"thread_id": "unit-native-stop-after-node-resume"}},
    )
    assert resumed["status"] == "completed"
    assert resumed["node_trace"][5]["node"] == "attach_market_snapshot"


def test_native_resume_boundary_synthesis_to_verify_claims(tmp_path: Path) -> None:
    memo_answer = {
        "schema_version": "sec_benchmark_agent_output_v0.1",
        "status": "answered",
        "answer_status": "answered_api_model",
        "answer": {"summary": "AMD capex memo"},
        "limitations": [],
    }
    memo_path = tmp_path / "qwen" / "agent_outputs.jsonl"

    def synthesize_answer(_state):
        _write_jsonl(memo_path, [memo_answer])
        return {"memo_answer": memo_answer, "artifact_refs": {"memo_answer": str(memo_path)}}

    graph = build_native_state_smoke_graph(
        synthesize_answer=synthesize_answer,
        stop_after_node="synthesize_answer",
    )
    result = graph.invoke(
        _native_resume_base_state(tmp_path),
        config={"configurable": {"thread_id": "unit-native-boundary-synthesis"}},
    )
    checkpoint_path = tmp_path / "langgraph_node_checkpoints.json"

    assert result["status"] == "stopped_after_node"
    inspection = inspect_node_checkpoint_artifact(checkpoint_path)
    assert inspection["resume_supported"] is True
    assert inspection["next_recoverable_node"] == "verify_claims"
    hydrated = hydrate_native_state_from_checkpoint_artifact(checkpoint_path)
    assert hydrated["state"]["memo_answer"]["agent_status"] == "answered"
    assert hydrated["state"]["memo_answer"]["claim_status"] == "not_verified"
    assert hydrated["state"]["memo_answer"]["score_status"] == "unknown"
    assert hydrated["state"]["memo_answer"]["answer"]["summary"] == "AMD capex memo"

    claim_path = tmp_path / "qwen" / "claim_verification.jsonl"

    def verify_claims(state):
        assert state["memo_answer"]["claim_status"] == "not_verified"
        assert state["context_rows"][0]["evidence_id"] == "AMD_SEC"
        claim = {"status": "verified", "claims": [], "unsupported_claim_count": 0}
        _write_jsonl(claim_path, [claim])
        return {
            "memo_answer": {**state["memo_answer"], "claim_status": "verified"},
            "claim_verification": claim,
            "artifact_refs": {"claim_verification": str(claim_path)},
        }

    resume_graph = build_native_state_smoke_graph(
        entry_node=hydrated["next_recoverable_node"],
        verify_claims=verify_claims,
        stop_after_node="verify_claims",
    )
    resumed = resume_graph.invoke(
        hydrated["state"],
        config={"configurable": {"thread_id": "unit-native-boundary-synthesis-resume"}},
    )
    assert resumed["status"] == "stopped_after_node"
    assert resumed["claim_verification"]["status"] == "verified"


def test_native_resume_boundary_verify_claims_to_gates(tmp_path: Path) -> None:
    state = _native_resume_base_state(tmp_path)
    memo = {"answer_status": "answered_api_model", "claim_status": "verified", "answer": {"summary": "AMD capex memo"}}
    claim = {"status": "verified", "claims": [], "unsupported_claim_count": 0}
    memo_path = _write_jsonl(tmp_path / "qwen" / "agent_outputs.jsonl", [memo])
    claim_path = _write_jsonl(tmp_path / "qwen" / "claim_verification.jsonl", [claim])
    state.update(
        {
            "memo_answer": memo,
            "claim_verification": claim,
            "artifact_refs": {**state["artifact_refs"], "memo_answer": str(memo_path), "claim_verification": str(claim_path)},
        }
    )

    graph = build_native_state_smoke_graph(stop_after_node="verify_claims")
    result = graph.invoke(state, config={"configurable": {"thread_id": "unit-native-boundary-verify"}})
    checkpoint_path = tmp_path / "langgraph_node_checkpoints.json"

    assert result["status"] == "stopped_after_node"
    inspection = inspect_node_checkpoint_artifact(checkpoint_path)
    assert inspection["resume_supported"] is True
    assert inspection["next_recoverable_node"] == "run_deterministic_gates"
    hydrated = hydrate_native_state_from_checkpoint_artifact(checkpoint_path)
    assert hydrated["state"]["claim_verification"]["status"] == "verified"

    gates = {"status": "completed", "ok": True, "summary": {"numeric_gate_pass": True}}
    gates_path = tmp_path / "post_gates" / "deterministic_gates.json"

    def run_deterministic_gates(state):
        assert state["claim_verification"]["status"] == "verified"
        _write_json(gates_path, gates)
        return {"deterministic_gates": gates, "artifact_refs": {"deterministic_gates": str(gates_path)}}

    resume_graph = build_native_state_smoke_graph(
        entry_node=hydrated["next_recoverable_node"],
        run_deterministic_gates=run_deterministic_gates,
        stop_after_node="run_deterministic_gates",
    )
    resumed = resume_graph.invoke(
        hydrated["state"],
        config={"configurable": {"thread_id": "unit-native-boundary-verify-resume"}},
    )
    assert resumed["status"] == "stopped_after_node"
    assert resumed["deterministic_gates"]["ok"] is True


def test_native_resume_boundary_gates_to_render(tmp_path: Path) -> None:
    state = _native_resume_base_state(tmp_path)
    memo = {"answer_status": "answered_api_model", "claim_status": "verified", "answer": {"summary": "AMD capex memo"}}
    claim = {"status": "verified", "claims": [], "unsupported_claim_count": 0}
    gates = {"status": "completed", "ok": True, "summary": {"numeric_gate_pass": True}}
    memo_path = _write_jsonl(tmp_path / "qwen" / "agent_outputs.jsonl", [memo])
    claim_path = _write_jsonl(tmp_path / "qwen" / "claim_verification.jsonl", [claim])
    gates_path = _write_json(tmp_path / "post_gates" / "deterministic_gates.json", gates)
    state.update(
        {
            "memo_answer": memo,
            "claim_verification": claim,
            "deterministic_gates": gates,
            "artifact_refs": {
                **state["artifact_refs"],
                "memo_answer": str(memo_path),
                "claim_verification": str(claim_path),
                "deterministic_gates": str(gates_path),
            },
        }
    )

    graph = build_native_state_smoke_graph(stop_after_node="run_deterministic_gates")
    result = graph.invoke(state, config={"configurable": {"thread_id": "unit-native-boundary-gates"}})
    checkpoint_path = tmp_path / "langgraph_node_checkpoints.json"

    assert result["status"] == "stopped_after_node"
    inspection = inspect_node_checkpoint_artifact(checkpoint_path)
    assert inspection["resume_supported"] is True
    assert inspection["next_recoverable_node"] == "render_answer"
    hydrated = hydrate_native_state_from_checkpoint_artifact(checkpoint_path)
    assert hydrated["state"]["deterministic_gates"]["ok"] is True

    rendered_path = tmp_path / "qwen" / "rendered_answer.md"

    def render_answer(state):
        assert state["deterministic_gates"]["ok"] is True
        rendered = "# SEC Agent Answer\n\nRendered memo"
        rendered_path.write_text(rendered, encoding="utf-8")
        return {"rendered_answer": rendered, "artifact_refs": {"rendered_answer": str(rendered_path)}}

    resume_graph = build_native_state_smoke_graph(
        entry_node=hydrated["next_recoverable_node"],
        render_answer=render_answer,
        stop_after_node="render_answer",
    )
    resumed = resume_graph.invoke(
        hydrated["state"],
        config={"configurable": {"thread_id": "unit-native-boundary-gates-resume"}},
    )
    assert resumed["status"] == "stopped_after_node"
    assert resumed["rendered_answer"].startswith("# SEC Agent Answer")


def test_native_graph_accepts_injected_planner(tmp_path: Path) -> None:
    def planner(state):
        assert state["user_query"] == "比较这些公司"
        return {
            "query_contract": {
                "task_type": "open_analysis",
                "search_scope_tickers": ["NVDA", "AMD", "JPM", "XOM"],
                "focus_tickers": ["NVDA", "AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
                "decomposed_tasks": [
                    {
                        "task_id": "representative_analysis",
                        "question_zh": "用代表公司分析。",
                        "priority": "primary",
                        "required_tickers": ["NVDA", "AMD"],
                        "required_metric_families": ["revenue"],
                    }
                ],
            },
            "selected_tickers": ["NVDA", "AMD", "JPM", "XOM"],
            "selected_years": [2026],
            "project_inventory": {"inventory_digest": "fake"},
        }

    graph = build_native_state_smoke_graph(plan_query=planner)
    result = graph.invoke(
        make_native_smoke_state(user_query="比较这些公司", output_dir=tmp_path),
        config={"configurable": {"thread_id": "unit-native-planner"}},
    )

    assert result["query_contract"]["search_scope_tickers"] == ["NVDA", "AMD", "JPM", "XOM"]
    assert result["query_contract"]["scope_mode"] == "sector_representative"
    assert result["selected_tickers"] == ["NVDA", "AMD", "JPM", "XOM"]
    assert result["node_trace"][1]["metadata"]["planner"] == "injected"


def test_native_graph_accepts_injected_retrieval(tmp_path: Path) -> None:
    def planner(_state):
        return {
            "query_contract": {
                "task_type": "open_analysis",
                "search_scope_tickers": ["NVDA", "AMD"],
                "focus_tickers": ["NVDA", "AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
                "decomposed_tasks": [
                    {
                        "task_id": "compare_revenue",
                        "question_zh": "比较收入。",
                        "priority": "primary",
                        "required_tickers": ["NVDA", "AMD"],
                        "required_metric_families": ["revenue"],
                    }
                ],
            },
            "selected_tickers": ["NVDA", "AMD"],
            "selected_years": [2026],
        }

    def retrieve_context(state):
        assert state["retrieval_plan"]["routes"]
        return {
            "context_rows": [
                {
                    "evidence_id": "NVDA_2026_10Q_REVENUE",
                    "ticker": "NVDA",
                    "fiscal_year": 2026,
                    "form_type": "10-Q",
                    "source_tier": "primary_sec_filing",
                    "text": "NVIDIA revenue discussion",
                }
            ],
            "retrieval_trace": {"case_id": "unit", "context_rows": []},
            "context_runtime": {"context_runner": "fake"},
            "artifact_refs": {"retrieved_context": str(tmp_path / "trace_logs.jsonl")},
        }

    graph = build_native_state_smoke_graph(plan_query=planner, retrieve_context=retrieve_context)
    result = graph.invoke(
        make_native_smoke_state(user_query="比较 NVDA 和 AMD", output_dir=tmp_path),
        config={"configurable": {"thread_id": "unit-native-retrieval"}},
    )

    assert result["context_rows"][0]["evidence_id"] == "NVDA_2026_10Q_REVENUE"
    assert result["context_runtime"]["context_runner"] == "fake"
    assert result["artifact_refs"]["retrieved_context"].endswith("trace_logs.jsonl")
    retrieval_node = [row for row in result["node_trace"] if row["node"] == "execute_retrieval_routes"][0]
    assert retrieval_node["metadata"]["mode"] == "injected"
    assert retrieval_node["metadata"]["context_row_count"] == 1


def test_native_graph_accepts_market_and_ledger_adapters(tmp_path: Path) -> None:
    def planner(_state):
        return {
            "query_contract": {
                "task_type": "open_analysis",
                "search_scope_tickers": ["NVDA"],
                "focus_tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing", "market_snapshot"],
                "metric_families": ["revenue"],
                "decomposed_tasks": [
                    {
                        "task_id": "nvda_revenue",
                        "question_zh": "分析收入和市场反应。",
                        "priority": "primary",
                        "required_tickers": ["NVDA"],
                        "required_metric_families": ["revenue"],
                    }
                ],
            },
            "selected_tickers": ["NVDA"],
            "selected_years": [2026],
        }

    def retrieve_context(_state):
        return {
            "context_rows": [{"evidence_id": "NVDA_SEC", "ticker": "NVDA", "text": "SEC context"}],
            "retrieval_trace": {"context_rows": []},
            "context_runtime": {"context_runner": "fake"},
        }

    def attach_market_snapshot(state):
        rows = [
            *state["context_rows"],
            {
                "evidence_id": "NVDA_MARKET",
                "ticker": "NVDA",
                "source_tier": "market_snapshot",
                "text": "market context",
            },
        ]
        return {
            "context_rows": rows,
            "market_snapshot_rows": [rows[-1]],
            "retrieval_trace": {"context_rows": rows},
        }

    def build_runtime_ledger(state):
        assert any(row["evidence_id"] == "NVDA_MARKET" for row in state["context_rows"])
        return {
            "runtime_ledger_rows": [
                {
                    "metric_id": "NVDA_REVENUE",
                    "ticker": "NVDA",
                    "fiscal_year": 2026,
                    "metric_family": "revenue",
                    "value": 1,
                }
            ],
            "artifact_refs": {"runtime_exact_value_ledger": str(tmp_path / "ledger.json")},
        }

    def build_coverage_matrix(state):
        assert state["runtime_ledger_rows"]
        return {
            "coverage_matrix": {
                "summary": {
                    "coverage_complete": True,
                    "primary_task_support_complete": True,
                    "context_row_count": len(state["context_rows"]),
                    "ledger_row_count": len(state["runtime_ledger_rows"]),
                }
            },
            "artifact_refs": {"evidence_coverage_matrix": str(tmp_path / "coverage.json")},
        }

    graph = build_native_state_smoke_graph(
        plan_query=planner,
        retrieve_context=retrieve_context,
        attach_market_snapshot=attach_market_snapshot,
        build_runtime_ledger=build_runtime_ledger,
        build_coverage_matrix=build_coverage_matrix,
    )
    result = graph.invoke(
        make_native_smoke_state(user_query="分析 NVDA", output_dir=tmp_path),
        config={"configurable": {"thread_id": "unit-native-market-ledger"}},
    )

    assert result["market_snapshot_rows"][0]["evidence_id"] == "NVDA_MARKET"
    assert result["runtime_ledger_rows"][0]["metric_id"] == "NVDA_REVENUE"
    ledger_node = [row for row in result["node_trace"] if row["node"] == "build_runtime_ledger"][0]
    assert ledger_node["metadata"]["mode"] == "injected"
    assert ledger_node["metadata"]["ledger_row_count"] == 1
    coverage_node = [row for row in result["node_trace"] if row["node"] == "assess_evidence_coverage"][0]
    assert coverage_node["metadata"]["mode"] == "injected"
    assert result["coverage_matrix"]["summary"]["coverage_complete"] is True
    assert result["evidence_sufficiency_report"]["sufficiency_level"] == "sufficient"


def test_native_graph_accepts_judgment_plan_adapter(tmp_path: Path) -> None:
    def planner(_state):
        return {
            "query_contract": {
                "task_type": "open_analysis",
                "search_scope_tickers": ["AMD"],
                "focus_tickers": ["AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "decomposed_tasks": [
                    {
                        "task_id": "amd_capex",
                        "question_zh": "分析 AMD 资本开支。",
                        "priority": "primary",
                        "required_tickers": ["AMD"],
                        "required_metric_families": ["capex"],
                    }
                ],
            },
            "selected_tickers": ["AMD"],
            "selected_years": [2026],
        }

    def retrieve_context(_state):
        return {
            "context_rows": [{"evidence_id": "AMD_SEC", "ticker": "AMD", "text": "AMD capex context"}],
            "retrieval_trace": {"context_rows": []},
        }

    def build_runtime_ledger(_state):
        return {
            "runtime_ledger_rows": [
                {
                    "metric_id": "AMD_CAPEX",
                    "ticker": "AMD",
                    "fiscal_year": 2026,
                    "metric_family": "capex",
                    "value": 1,
                }
            ]
        }

    def build_coverage_matrix(_state):
        return {
            "coverage_matrix": {
                "summary": {
                    "coverage_complete": True,
                    "primary_task_support_complete": True,
                }
            }
        }

    def build_judgment_plan(state):
        assert state["runtime_ledger_rows"]
        assert state["coverage_matrix"]["summary"]["coverage_complete"] is True
        return {
            "judgment_plan": {
                "case_id": "INTERACTIVE_unit",
                "drivers": [{"claim": "AMD capex is supported.", "rank": 1}],
            },
            "artifact_refs": {"judgment_plan": str(tmp_path / "runtime_judgment_plan.json")},
        }

    graph = build_native_state_smoke_graph(
        plan_query=planner,
        retrieve_context=retrieve_context,
        build_runtime_ledger=build_runtime_ledger,
        build_coverage_matrix=build_coverage_matrix,
        build_judgment_plan=build_judgment_plan,
    )
    result = graph.invoke(
        make_native_smoke_state(user_query="分析 AMD 资本开支", output_dir=tmp_path),
        config={"configurable": {"thread_id": "unit-native-judgment-plan"}},
    )

    assert result["judgment_plan"]["drivers"][0]["claim"] == "AMD capex is supported."
    plan_node = [row for row in result["node_trace"] if row["node"] == "build_judgment_plan"][0]
    assert plan_node["metadata"]["mode"] == "injected"
    assert plan_node["metadata"]["driver_count"] == 1


def test_native_graph_accepts_synthesis_adapter(tmp_path: Path) -> None:
    def synthesize_answer(state):
        assert state["judgment_plan"]["drivers"]
        return {
            "memo_answer": {
                "answer_status": "answered_api_model",
                "claim_status": "not_verified",
                "answer": {"summary": "AMD capex memo"},
            },
            "rendered_answer": "# SEC Agent Answer\n\nAMD capex memo",
            "artifact_refs": {"memo_answer": str(tmp_path / "agent_outputs.jsonl")},
        }

    graph = build_native_state_smoke_graph(synthesize_answer=synthesize_answer)
    initial = make_native_smoke_state(
        user_query="分析 AMD 资本开支",
        output_dir=tmp_path,
        query_contract={
            "task_type": "open_analysis",
            "search_scope_tickers": ["AMD"],
            "focus_tickers": ["AMD"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["capex"],
            "decomposed_tasks": [
                {
                    "task_id": "amd_capex",
                    "question_zh": "分析 AMD 资本开支。",
                    "priority": "primary",
                    "required_tickers": ["AMD"],
                    "required_metric_families": ["capex"],
                }
            ],
        },
    )
    initial["judgment_plan"] = {"drivers": [{"rank": 1, "claim": "AMD capex is supported."}]}

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-native-synthesis"}})

    assert result["memo_answer"]["answer"]["summary"] == "AMD capex memo"
    synth_node = [row for row in result["node_trace"] if row["node"] == "synthesize_answer"][0]
    assert synth_node["metadata"]["mode"] == "injected"
    assert synth_node["metadata"]["answer_status"] == "answered_api_model"
    assert result["claim_verification"]["status"] == "not_run"


def test_native_graph_accepts_verify_claims_adapter(tmp_path: Path) -> None:
    def synthesize_answer(_state):
        return {
            "memo_answer": {
                "answer_status": "answered_api_model",
                "claim_status": "not_verified",
                "answer": {"summary": "AMD capex memo"},
            },
            "artifact_refs": {"memo_answer": str(tmp_path / "agent_outputs.jsonl")},
        }

    def verify_claims(state):
        assert state["memo_answer"]["claim_status"] == "not_verified"
        return {
            "memo_answer": {**state["memo_answer"], "claim_status": "verified", "claims": []},
            "claim_verification": {"status": "verified", "claims": [], "unsupported_claim_count": 0},
            "artifact_refs": {"claim_verification": str(tmp_path / "claim_verification.jsonl")},
        }

    graph = build_native_state_smoke_graph(synthesize_answer=synthesize_answer, verify_claims=verify_claims)
    initial = make_native_smoke_state(
        user_query="分析 AMD",
        output_dir=tmp_path,
        query_contract={
            "task_type": "open_analysis",
            "search_scope_tickers": ["AMD"],
            "focus_tickers": ["AMD"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["revenue"],
            "decomposed_tasks": [
                {
                    "task_id": "amd_revenue",
                    "question_zh": "分析 AMD 收入。",
                    "priority": "primary",
                    "required_tickers": ["AMD"],
                    "required_metric_families": ["revenue"],
                }
            ],
        },
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-native-verify-claims"}})

    assert result["claim_verification"]["status"] == "verified"
    verify_node = [row for row in result["node_trace"] if row["node"] == "verify_claims"][0]
    assert verify_node["metadata"]["mode"] == "injected"
    assert verify_node["metadata"]["unsupported_claim_count"] == 0
    verify_checkpoint = [row for row in result["node_checkpoints"] if row["node"] == "verify_claims"][0]
    assert verify_checkpoint["state_summary"]["claim_status"] == "verified"
    assert verify_checkpoint["state_summary"]["claim_verification_status"] == "verified"
    assert "claim_verification" in verify_checkpoint["state_summary"]["artifact_keys"]


def test_native_graph_accepts_gates_and_renderer_adapters(tmp_path: Path) -> None:
    def run_deterministic_gates(_state):
        return {
            "deterministic_gates": {"status": "completed", "ok": True, "summary": {"numeric_gate_pass": True}},
            "artifact_refs": {"deterministic_gates": str(tmp_path / "gates.json")},
        }

    def render_answer(state):
        assert state["deterministic_gates"]["ok"] is True
        return {
            "rendered_answer": "# SEC Agent Answer\n\nRendered memo",
            "artifact_refs": {"rendered_answer": str(tmp_path / "rendered_answer.md")},
        }

    graph = build_native_state_smoke_graph(
        run_deterministic_gates=run_deterministic_gates,
        render_answer=render_answer,
    )
    initial = make_native_smoke_state(
        user_query="分析 AMD",
        output_dir=tmp_path,
        query_contract={
            "task_type": "open_analysis",
            "search_scope_tickers": ["AMD"],
            "focus_tickers": ["AMD"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["revenue"],
            "decomposed_tasks": [
                {
                    "task_id": "amd_revenue",
                    "question_zh": "分析 AMD 收入。",
                    "priority": "primary",
                    "required_tickers": ["AMD"],
                    "required_metric_families": ["revenue"],
                }
            ],
        },
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-native-gates-render"}})

    assert result["deterministic_gates"]["ok"] is True
    assert result["rendered_answer"].startswith("# SEC Agent Answer")
    gate_node = [row for row in result["node_trace"] if row["node"] == "run_deterministic_gates"][0]
    render_node = [row for row in result["node_trace"] if row["node"] == "render_answer"][0]
    assert gate_node["metadata"]["mode"] == "injected"
    assert render_node["metadata"]["mode"] == "injected"
    gate_checkpoint = [row for row in result["node_checkpoints"] if row["node"] == "run_deterministic_gates"][0]
    render_checkpoint = [row for row in result["node_checkpoints"] if row["node"] == "render_answer"][0]
    assert gate_checkpoint["state_summary"]["deterministic_gates_ok"] is True
    assert render_checkpoint["state_summary"]["rendered_answer_chars"] > 0


def test_native_graph_sufficiency_report_emits_second_pass_requests(tmp_path: Path) -> None:
    graph = build_native_state_smoke_graph()
    initial = make_native_smoke_state(
        user_query="分析 AMD 资本开支",
        output_dir=tmp_path,
        query_contract={
            "task_type": "open_analysis",
            "search_scope_tickers": ["AMD"],
            "focus_tickers": ["AMD"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["capex"],
        },
    )
    initial["context_rows"] = [{"evidence_id": "AMD_CONTEXT", "ticker": "AMD"}]
    initial["coverage_matrix"] = {
        "summary": {
            "coverage_complete": False,
            "primary_task_support_complete": False,
            "answer_status": "partial",
        },
        "tasks": [
            {
                "task_id": "amd_capex",
                "priority": "primary",
                "support_level": "insufficient",
                "missing_focus_tickers": ["AMD"],
                "missing_years": [2026],
                "missing_filing_types": ["10-Q"],
                "missing_source_tiers": ["primary_sec_filing"],
                "missing_metric_families": ["capex"],
            }
        ],
    }

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-native-sufficiency"}})
    report = result["evidence_sufficiency_report"]

    assert report["sufficiency_level"] == "partial"
    assert report["bounded_answer_allowed"] is True
    assert report["second_pass_retrieval_requests"][0]["tickers"] == ["AMD"]
    assert report["second_pass_retrieval_requests"][0]["metric_families"] == ["capex"]


def test_native_graph_conditional_second_pass_runs_once(tmp_path: Path) -> None:
    def planner(_state):
        return {
            "query_contract": {
                "task_type": "open_analysis",
                "search_scope_tickers": ["AMD"],
                "focus_tickers": ["AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "decomposed_tasks": [
                    {
                        "task_id": "amd_capex",
                        "question_zh": "分析 AMD 资本开支。",
                        "priority": "primary",
                        "required_tickers": ["AMD"],
                        "required_metric_families": ["capex"],
                    }
                ],
            },
            "selected_tickers": ["AMD"],
            "selected_years": [2026],
        }

    def retrieve_context(_state):
        return {
            "context_rows": [{"evidence_id": "AMD_INITIAL", "ticker": "AMD", "text": "initial"}],
            "retrieval_trace": {"context_rows": []},
            "context_runtime": {"context_runner": "fake"},
        }

    def build_runtime_ledger(state):
        rows = []
        if any(row.get("evidence_id") == "AMD_SECOND_PASS" for row in state["context_rows"]):
            rows.append(
                {
                    "metric_id": "AMD_CAPEX",
                    "ticker": "AMD",
                    "fiscal_year": 2026,
                    "metric_family": "capex",
                    "value": 1,
                }
            )
        return {"runtime_ledger_rows": rows}

    def build_coverage_matrix(state):
        if state.get("second_pass_attempts"):
            return {
                "coverage_matrix": {
                    "summary": {
                        "coverage_complete": True,
                        "primary_task_support_complete": True,
                        "answer_status": "complete",
                    },
                    "tasks": [{"task_id": "amd_capex", "support_level": "strong", "priority": "primary"}],
                }
            }
        return {
            "coverage_matrix": {
                "summary": {
                    "coverage_complete": False,
                    "primary_task_support_complete": False,
                    "answer_status": "partial",
                },
                "tasks": [
                    {
                        "task_id": "amd_capex",
                        "priority": "primary",
                        "support_level": "insufficient",
                        "missing_focus_tickers": ["AMD"],
                        "missing_years": [2026],
                        "missing_filing_types": ["10-Q"],
                        "missing_source_tiers": ["primary_sec_filing"],
                        "missing_metric_families": ["capex"],
                    }
                ],
            }
        }

    def execute_second_pass_retrieval(state):
        assert state["evidence_sufficiency_report"]["second_pass_retrieval_requests"]
        return {
            "context_rows": [
                *state["context_rows"],
                {"evidence_id": "AMD_SECOND_PASS", "ticker": "AMD", "text": "second pass"},
            ],
            "retrieval_trace": {"context_rows": []},
            "second_pass_attempts": 1,
            "second_pass_result": {"triggered": True, "added_context_row_count": 1},
        }

    graph = build_native_state_smoke_graph(
        plan_query=planner,
        retrieve_context=retrieve_context,
        build_runtime_ledger=build_runtime_ledger,
        build_coverage_matrix=build_coverage_matrix,
        execute_second_pass_retrieval=execute_second_pass_retrieval,
    )
    result = graph.invoke(
        make_native_smoke_state(user_query="分析 AMD 资本开支", output_dir=tmp_path),
        config={"configurable": {"thread_id": "unit-native-second-pass"}},
    )
    nodes = [row["node"] for row in result["node_trace"]]

    assert nodes.count("execute_second_pass_retrieval") == 1
    assert nodes.count("build_runtime_ledger") == 2
    assert nodes.count("assess_evidence_coverage") == 2
    assert nodes.count("assess_evidence_sufficiency") == 2
    assert result["second_pass_attempts"] == 1
    assert result["second_pass_result"]["added_context_row_count"] == 1
    assert result["evidence_sufficiency_report"]["sufficiency_level"] == "sufficient"
    assert any(row["evidence_id"] == "AMD_SECOND_PASS" for row in result["context_rows"])


def test_llm_planner_scope_contract_keeps_system_search_scope_and_records_representatives() -> None:
    interactive = _load_interactive_module()
    inventory = {
        "inventory_digest": "planner-scope-test",
        "companies": [
            {
                "ticker": ticker,
                "category": "mixed",
                "filings": [{"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"}],
            }
            for ticker in ["NVDA", "AMD", "JPM", "XOM"]
        ],
        "categories": [{"category": "mixed", "tickers": ["NVDA", "AMD", "JPM", "XOM"]}],
    }
    fallback = {
        "task_type": "open_analysis",
        "search_scope_tickers": ["NVDA", "AMD", "JPM", "XOM"],
        "focus_tickers": ["NVDA", "AMD", "JPM", "XOM"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["revenue"],
        "decomposed_tasks": [
            {
                "task_id": "cross_sector",
                "question_zh": "比较跨行业表现。",
                "priority": "primary",
                "required_tickers": ["NVDA", "AMD", "JPM", "XOM"],
                "required_metric_families": ["revenue"],
            },
            {
                "task_id": "boundary",
                "question_zh": "说明代表样本边界。",
                "priority": "supporting",
                "required_tickers": ["NVDA", "AMD"],
                "required_metric_families": ["revenue"],
            },
        ],
    }
    planned = {
        "task_type": "open_analysis",
        "scope_mode": "sector_representative",
        "search_scope_tickers": ["NVDA", "AMD"],
        "focus_tickers": ["NVDA", "AMD"],
        "representative_tickers": ["NVDA", "AMD"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["revenue"],
        "decomposed_tasks": [
            {
                "task_id": "ai_representatives",
                "question_zh": "用代表公司解释 AI 相关表现。",
                "priority": "primary",
                "required_tickers": ["NVDA", "AMD"],
                "required_metric_families": ["revenue"],
            },
            {
                "task_id": "scope_boundary",
                "question_zh": "说明完整 universe 中未展开公司的边界。",
                "priority": "supporting",
                "required_tickers": ["NVDA", "AMD"],
                "required_metric_families": ["revenue"],
            },
        ],
    }

    clean = interactive._normalize_llm_query_contract(
        planned,
        fallback,
        ["NVDA", "AMD", "JPM", "XOM"],
        [2026],
        inventory,
    )
    clean = interactive._validate_query_contract(clean, ["NVDA", "AMD", "JPM", "XOM"], [2026], inventory)

    assert clean["search_scope_tickers"] == ["NVDA", "AMD", "JPM", "XOM"]
    assert clean["focus_tickers"] == ["NVDA", "AMD"]
    assert clean["scope_mode"] == "sector_representative"
    assert clean["scope"]["universe_count"] == 4
    assert clean["scope"]["focus_count"] == 2
    assert clean["scope"]["representative_tickers"] == ["NVDA", "AMD"]


def test_planner_prompt_exposes_scope_mode_and_evidence_requirement_contract() -> None:
    interactive = _load_interactive_module()
    prompt = interactive._query_planner_system_prompt(
        {
            "inventory_digest": "prompt-scope-test",
            "companies": [
                {
                    "ticker": "NVDA",
                    "company": "NVIDIA",
                    "category": "semiconductor",
                    "filings": [{"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"}],
                }
            ],
            "categories": [{"category": "semiconductor", "tickers": ["NVDA"]}],
        },
        ["NVDA"],
        [2026],
    )

    assert "scope_mode" in prompt
    assert "search_scope_tickers" in prompt
    assert "representative_tickers" in prompt
    assert "evidence_requirements" in prompt


def test_interactive_graph_planner_adapter_preserves_full_all_scope(tmp_path: Path, monkeypatch) -> None:
    interactive = _load_interactive_module()
    manifest_path = tmp_path / "manifest.jsonl"
    rows = [
        {
            "ticker": ticker,
            "company": ticker,
            "fiscal_year": 2026,
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "category": "mixed",
        }
        for ticker in ["NVDA", "AMD", "JPM", "XOM"]
    ]
    manifest_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sec_agent_interactive.py",
            "--manifest-path",
            str(manifest_path),
            "--tickers",
            "ALL",
            "--years",
            "2026",
            "--query-planner",
            "heuristic",
        ],
    )
    args = interactive.parse_args()

    plan = interactive.build_query_plan_for_graph(args, "比较这些公司在 AI 相关业务上的表现")
    contract = plan["query_contract"]

    assert plan["selected_tickers"] == ["AMD", "JPM", "NVDA", "XOM"]
    assert contract["search_scope_tickers"] == ["AMD", "JPM", "NVDA", "XOM"]
    assert contract["scope"]["universe_count"] == 4
    assert contract["scope_mode"] in {"full_universe", "sector_representative"}


def test_interactive_graph_retrieval_adapter_writes_case_and_reads_trace(tmp_path: Path, monkeypatch) -> None:
    interactive = _load_interactive_module()

    def fake_run_context(_args, cases_path, trace_dir):
        assert cases_path.exists()
        trace_dir.mkdir(parents=True, exist_ok=True)
        interactive._write_jsonl(
            trace_dir / "trace_logs.jsonl",
            [
                {
                    "case_id": "unit_case",
                    "context_rows": [
                        {
                            "evidence_id": "AMD_2026_10Q_REVENUE",
                            "ticker": "AMD",
                            "fiscal_year": 2026,
                            "form_type": "10-Q",
                            "source_tier": "primary_sec_filing",
                            "text": "AMD revenue discussion",
                        }
                    ],
                }
            ],
        )
        return {"context_runtime": {"context_runner": "fake"}}

    monkeypatch.setattr(interactive, "_run_context", fake_run_context)
    result = interactive.retrieve_context_for_graph(
        Namespace(),
        {
            "user_query": "比较 AMD",
            "run_id": "unit_run",
            "output_dir": str(tmp_path),
            "selected_tickers": ["AMD"],
            "selected_years": [2026],
            "query_contract": {
                "task_type": "open_analysis",
                "search_scope_tickers": ["AMD"],
                "focus_tickers": ["AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
                "decomposed_tasks": [
                    {
                        "task_id": "amd_revenue",
                        "question_zh": "比较 AMD 收入。",
                        "priority": "primary",
                        "required_tickers": ["AMD"],
                        "required_metric_families": ["revenue"],
                    }
                ],
            },
        },
    )

    assert result["context_rows"][0]["evidence_id"] == "AMD_2026_10Q_REVENUE"
    assert result["context_runtime"]["context_runner"] == "fake"
    assert (tmp_path / "case.jsonl").exists()
    assert (tmp_path / "retrieval_plan.json").exists()
    assert result["artifact_refs"]["retrieved_context"].endswith("trace_logs.jsonl")


def test_interactive_graph_second_pass_adapter_executes_report_request(tmp_path: Path, monkeypatch) -> None:
    interactive = _load_interactive_module()

    def fake_run_context(_args, cases_path, trace_dir):
        assert "second_pass_retrieval_1" in str(cases_path)
        trace_dir.mkdir(parents=True, exist_ok=True)
        interactive._write_jsonl(
            trace_dir / "trace_logs.jsonl",
            [
                {
                    "case_id": "unit_second_pass",
                    "context_rows": [
                        {
                            "evidence_id": "AMD_2026_10Q_CAPEX",
                            "ticker": "AMD",
                            "fiscal_year": 2026,
                            "form_type": "10-Q",
                            "source_tier": "primary_sec_filing",
                            "text": "AMD capex discussion",
                        }
                    ],
                }
            ],
        )
        return {"context_runtime": {"context_runner": "fake"}}

    monkeypatch.setattr(interactive, "_run_context", fake_run_context)
    result = interactive.execute_second_pass_retrieval_for_graph(
        Namespace(),
        {
            "user_query": "分析 AMD 资本开支",
            "run_id": "unit_run",
            "output_dir": str(tmp_path),
            "selected_tickers": ["AMD"],
            "selected_years": [2026],
            "query_contract": {
                "task_type": "open_analysis",
                "search_scope_tickers": ["AMD"],
                "focus_tickers": ["AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "decomposed_tasks": [
                    {
                        "task_id": "amd_capex",
                        "question_zh": "分析 AMD 资本开支。",
                        "priority": "primary",
                        "required_tickers": ["AMD"],
                        "required_metric_families": ["capex"],
                    }
                ],
            },
            "context_rows": [{"evidence_id": "AMD_INITIAL", "ticker": "AMD", "text": "initial"}],
            "retrieval_trace": {"context_rows": []},
            "evidence_sufficiency_report": {
                "second_pass_retrieval_requests": [
                    {
                        "request_id": "second_pass_1",
                        "task_id": "amd_capex",
                        "tickers": ["AMD"],
                        "years": [2026],
                        "filing_types": ["10-Q"],
                        "source_tiers": ["primary_sec_filing"],
                        "metric_families": ["capex"],
                    }
                ]
            },
        },
    )

    assert result["second_pass_attempts"] == 1
    assert result["second_pass_result"]["triggered"] is True
    assert result["second_pass_result"]["added_context_row_count"] == 1
    assert any(row["evidence_id"] == "AMD_2026_10Q_CAPEX" for row in result["context_rows"])
    assert (tmp_path / "second_pass_retrieval_trace.json").exists()
    assert result["artifact_refs"]["second_pass_retrieved_context"].endswith("trace_logs.jsonl")


def test_interactive_graph_market_and_ledger_adapters_write_artifacts(tmp_path: Path, monkeypatch) -> None:
    interactive = _load_interactive_module()
    market_row = {
        "evidence_id": "AMD_MARKET",
        "ticker": "AMD",
        "source_tier": "market_snapshot",
        "snapshot_id": "unit_snapshot",
        "as_of_date": "2026-05-22",
        "text": "market snapshot row",
    }
    monkeypatch.setattr(interactive, "_load_market_context_rows", lambda _path, _contract: [market_row])
    monkeypatch.setattr(
        interactive,
        "_build_runtime_ledger",
        lambda case, context_rows, _args: [
            {
                "metric_id": "AMD_REVENUE",
                "ticker": "AMD",
                "fiscal_year": 2026,
                "metric_family": "revenue",
                "value": 1,
                "supporting_evidence_ids": [row.get("evidence_id") for row in context_rows],
            }
        ],
    )
    monkeypatch.setattr(
        interactive,
        "build_coverage_matrix",
        lambda **_kwargs: {
            "summary": {
                "coverage_complete": True,
                "primary_task_support_complete": True,
                "context_row_count": 2,
                "ledger_row_count": 1,
            }
        },
    )
    query_contract = {
        "task_type": "open_analysis",
        "search_scope_tickers": ["AMD"],
        "focus_tickers": ["AMD"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing", "market_snapshot"],
        "metric_families": ["revenue"],
        "market_snapshot": {"requested": True},
        "decomposed_tasks": [
            {
                "task_id": "amd_revenue_market",
                "question_zh": "分析 AMD 收入和市场反应。",
                "priority": "primary",
                "required_tickers": ["AMD"],
                "required_metric_families": ["revenue"],
            }
        ],
    }
    graph_state = {
        "user_query": "分析 AMD",
        "run_id": "unit_run",
        "output_dir": str(tmp_path),
        "selected_tickers": ["AMD"],
        "selected_years": [2026],
        "query_contract": query_contract,
        "context_rows": [{"evidence_id": "AMD_SEC", "ticker": "AMD", "text": "SEC row"}],
        "retrieval_trace": {"context_rows": []},
    }

    market_result = interactive.attach_market_snapshot_for_graph(
        Namespace(market_evidence_path="unit_market.jsonl"),
        graph_state,
    )
    ledger_result = interactive.build_runtime_ledger_for_graph(
        Namespace(),
        {**graph_state, "context_rows": market_result["context_rows"]},
    )
    coverage_result = interactive.build_coverage_matrix_for_graph(
        Namespace(),
        {
            **graph_state,
            "context_rows": market_result["context_rows"],
            "runtime_ledger_rows": ledger_result["runtime_ledger_rows"],
        },
    )

    assert market_result["market_snapshot_rows"][0]["evidence_id"] == "AMD_MARKET"
    assert (tmp_path / "market_snapshot_context_rows.jsonl").exists()
    assert ledger_result["runtime_ledger_rows"][0]["metric_id"] == "AMD_REVENUE"
    assert (tmp_path / "runtime_exact_value_ledger.json").exists()
    assert coverage_result["coverage_matrix"]["summary"]["coverage_complete"] is True
    assert (tmp_path / "runtime_evidence_coverage_matrix.json").exists()


def test_interactive_graph_judgment_plan_adapter_writes_artifacts(tmp_path: Path, monkeypatch) -> None:
    interactive = _load_interactive_module()

    def fake_run(cmd):
        output_path = Path(cmd[cmd.index("--output-path") + 1])
        report_path = Path(cmd[cmd.index("--report-path") + 1])
        cases_path = Path(cmd[cmd.index("--cases-path") + 1])
        ledger_path = Path(cmd[cmd.index("--ledger-path") + 1])
        case = interactive._single_jsonl(cases_path)
        ledger_rows = interactive._read_json(ledger_path)["rows"]
        assert ledger_rows[0]["case_id"] == case["case_id"]
        interactive._write_json(
            output_path,
            {
                "schema_version": "sec_benchmark_judgment_plan_seed_v0.1",
                "plans": [
                    {
                        "case_id": case["case_id"],
                        "drivers": [
                            {
                                "rank": 1,
                                "claim": "AMD capex is supported by the runtime ledger.",
                                "supporting_metric_ids": ["AMD_CAPEX"],
                                "supporting_evidence_ids": ["AMD_SEC"],
                            }
                        ],
                        "do_not_overstate": [],
                    }
                ],
                "skipped": [],
            },
        )
        interactive._write_json(report_path, {"summary": {"plan_count": 1}})

    monkeypatch.setattr(interactive, "_run", fake_run)
    result = interactive.build_judgment_plan_for_graph(
        Namespace(),
        {
            "user_query": "分析 AMD 资本开支",
            "run_id": "unit_run",
            "output_dir": str(tmp_path),
            "selected_tickers": ["AMD"],
            "selected_years": [2026],
            "query_contract": {
                "task_type": "open_analysis",
                "search_scope_tickers": ["AMD"],
                "focus_tickers": ["AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "decomposed_tasks": [
                    {
                        "task_id": "amd_capex",
                        "question_zh": "分析 AMD 资本开支。",
                        "priority": "primary",
                        "required_tickers": ["AMD"],
                        "required_metric_families": ["capex"],
                    }
                ],
            },
            "context_rows": [{"evidence_id": "AMD_SEC", "ticker": "AMD", "text": "AMD capex context"}],
            "retrieval_trace": {"case_id": "unit_case", "context_rows": []},
            "runtime_ledger_rows": [
                {
                    "metric_id": "AMD_CAPEX",
                    "ticker": "AMD",
                    "fiscal_year": 2026,
                    "metric_family": "capex",
                    "value": 1,
                }
            ],
            "coverage_matrix": {
                "summary": {
                    "coverage_complete": True,
                    "primary_task_support_complete": True,
                }
            },
        },
    )

    assert result["judgment_plan"]["drivers"][0]["claim"].startswith("AMD capex")
    assert (tmp_path / "case.jsonl").exists()
    assert (tmp_path / "trace" / "trace_logs.jsonl").exists()
    assert (tmp_path / "runtime_exact_value_ledger.json").exists()
    assert (tmp_path / "runtime_judgment_plan.json").exists()
    assert result["artifact_refs"]["judgment_plan"].endswith("runtime_judgment_plan.json")


def test_interactive_graph_synthesis_adapter_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    interactive = _load_interactive_module()
    monkeypatch.setattr(interactive, "_ensure_llm_ready", lambda _args: None)
    monkeypatch.setattr(
        interactive,
        "_ask_llm_server",
        lambda *_args, **_kwargs: ('{"summary":"AMD capex memo"}', {"provider": "unit", "model": "fake"}),
    )
    monkeypatch.setattr(
        interactive,
        "_normalize_or_fallback",
        lambda *_args, **_kwargs: ({"summary": "AMD capex memo"}, "parsed", {"summary": "AMD capex memo"}),
    )
    args = Namespace(
        llm_backend="deepseek",
        model="unit-model",
        base_url="https://unit.invalid",
        chat_completions_path="/chat/completions",
        api_key_env="UNIT_API_KEY",
    )
    result = interactive.synthesize_answer_for_graph(
        args,
        {
            "user_query": "分析 AMD 资本开支",
            "run_id": "unit_run",
            "output_dir": str(tmp_path),
            "selected_tickers": ["AMD"],
            "selected_years": [2026],
            "query_contract": {
                "task_type": "open_analysis",
                "search_scope_tickers": ["AMD"],
                "focus_tickers": ["AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "decomposed_tasks": [
                    {
                        "task_id": "amd_capex",
                        "question_zh": "分析 AMD 资本开支。",
                        "priority": "primary",
                        "required_tickers": ["AMD"],
                        "required_metric_families": ["capex"],
                    }
                ],
            },
            "context_rows": [
                {
                    "evidence_id": "AMD_SEC",
                    "ticker": "AMD",
                    "fiscal_year": 2026,
                    "source_tier": "primary_sec_filing",
                    "text": "AMD capex context",
                }
            ],
            "retrieval_trace": {"case_id": "INTERACTIVE_unit_run", "mode": "pipeline_context"},
            "runtime_ledger_rows": [
                {
                    "metric_id": "AMD_CAPEX",
                    "ticker": "AMD",
                    "fiscal_year": 2026,
                    "metric_family": "capex",
                    "value": 1,
                    "supporting_evidence_ids": ["AMD_SEC"],
                }
            ],
            "coverage_matrix": {
                "summary": {"coverage_complete": True, "primary_task_support_complete": True},
                "tasks": [{"sample_evidence_ids": ["AMD_SEC"], "sample_metric_ids": ["AMD_CAPEX"]}],
            },
            "judgment_plan": {"drivers": [{"rank": 1, "claim": "AMD capex is supported."}]},
        },
    )

    assert result["memo_answer"]["answer"]["summary"] == "AMD capex memo"
    assert result["memo_answer"]["claim_status"] == "not_verified"
    assert "claim_verification" not in result
    assert (tmp_path / "runtime_evidence_pack.json").exists()
    assert (tmp_path / "qwen" / "agent_outputs.jsonl").exists()
    assert (tmp_path / "qwen" / "rendered_answer.md").exists()


def test_interactive_graph_verify_claims_adapter_rewrites_outputs(tmp_path: Path, monkeypatch) -> None:
    interactive = _load_interactive_module()
    qwen_dir = tmp_path / "qwen"
    qwen_dir.mkdir(parents=True)
    memo_answer = {
        "agent_status": "answered",
        "answer_status": "answered_api_model",
        "answer": {"summary": "AMD capex memo"},
        "limitations": [],
        "claim_status": "not_verified",
        "claims": [],
        "unsupported_claim_count": 0,
        "score_status": "scored_backend",
        "score_total": 8.8,
        "failure_types": [],
        "score_notes": ["claim_first_pending_native_verify_node"],
        "debug": {"user_query": "分析 AMD 资本开支", "raw_answer": {"summary": "AMD capex memo"}},
    }
    interactive._write_jsonl(
        qwen_dir / "trace_logs.jsonl",
        [
            {
                "case_id": "INTERACTIVE_unit_run",
                "mode": "pipeline_context",
                "context_rows": [{"evidence_id": "AMD_TRACE_ONLY", "ticker": "AMD", "text": "older selected pack"}],
            }
        ],
    )

    def fake_verify_answer_claims(**kwargs):
        assert [row["evidence_id"] for row in kwargs["context_rows"]] == ["AMD_SEC"]
        return {
            "answer": kwargs["answer"],
            "claims": [{"claim": "AMD capex memo", "status": "supported"}],
            "claim_status": "verified",
            "unsupported_claim_count": 0,
            "summary": {
                "candidate_count": 1,
                "promoted_count": 1,
                "downgraded_count": 0,
                "rejected_count": 0,
            },
        }

    monkeypatch.setattr(
        interactive,
        "verify_answer_claims",
        fake_verify_answer_claims,
    )
    result = interactive.verify_claims_for_graph(
        Namespace(),
        {
            "user_query": "分析 AMD 资本开支",
            "run_id": "unit_run",
            "output_dir": str(tmp_path),
            "memo_answer": memo_answer,
            "context_rows": [{"evidence_id": "AMD_SEC", "ticker": "AMD", "text": "full graph state context"}],
            "runtime_ledger_rows": [
                {
                    "metric_id": "AMD_CAPEX",
                    "ticker": "AMD",
                    "fiscal_year": 2026,
                    "metric_family": "capex",
                    "value": 1,
                    "supporting_evidence_ids": ["AMD_SEC"],
                }
            ],
            "judgment_plan": {"drivers": [{"rank": 1, "claim": "AMD capex is supported."}]},
        },
    )

    assert result["memo_answer"]["claim_status"] == "verified"
    assert result["claim_verification"]["status"] == "verified"
    assert result["claim_verification"]["unsupported_claim_count"] == 0
    assert (tmp_path / "qwen" / "claim_verification.jsonl").exists()
    assert (tmp_path / "qwen" / "agent_outputs.jsonl").exists()


def test_interactive_graph_gates_and_render_adapters_write_artifacts(tmp_path: Path, monkeypatch) -> None:
    interactive = _load_interactive_module()
    qwen_dir = tmp_path / "qwen"
    qwen_dir.mkdir(parents=True)
    interactive._write_jsonl(
        qwen_dir / "agent_outputs.jsonl",
        [{"case_id": "INTERACTIVE_unit_run", "status": "answered", "answer_status": "answered_api_model"}],
    )

    def fake_run_post_gates(_cases_path, _qwen_dir, _ledger_path, _plan_path, gate_dir, *, has_plan):
        assert has_plan is True
        interactive._write_json(
            gate_dir / "sec_benchmark_post_gates_summary.json",
            {"numeric_gate_pass": True, "citation_gate_pass": True},
        )

    monkeypatch.setattr(interactive, "_run_post_gates", fake_run_post_gates)
    graph_state = {
        "user_query": "分析 AMD",
        "run_id": "unit_run",
        "output_dir": str(tmp_path),
        "selected_tickers": ["AMD"],
        "selected_years": [2026],
        "query_contract": {
            "task_type": "open_analysis",
            "search_scope_tickers": ["AMD"],
            "focus_tickers": ["AMD"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["revenue"],
            "decomposed_tasks": [
                {
                    "task_id": "amd_revenue",
                    "question_zh": "分析 AMD 收入。",
                    "priority": "primary",
                    "required_tickers": ["AMD"],
                    "required_metric_families": ["revenue"],
                }
            ],
        },
        "context_rows": [{"evidence_id": "AMD_SEC", "ticker": "AMD", "text": "AMD revenue context"}],
        "runtime_ledger_rows": [
            {
                "metric_id": "AMD_REVENUE",
                "ticker": "AMD",
                "fiscal_year": 2026,
                "metric_family": "revenue",
                "value": 1,
            }
        ],
        "judgment_plan": {"case_id": "INTERACTIVE_unit_run", "drivers": [{"rank": 1, "claim": "AMD revenue"}]},
        "memo_answer": {"answer": {"summary": "AMD revenue memo"}},
    }

    gates_result = interactive.run_deterministic_gates_for_graph(Namespace(), graph_state)
    render_result = interactive.render_answer_for_graph(Namespace(), graph_state)

    assert gates_result["deterministic_gates"]["ok"] is True
    assert (tmp_path / "post_gates" / "sec_benchmark_post_gates_summary.json").exists()
    assert render_result["rendered_answer"].startswith("# SEC Agent Answer")
    assert (tmp_path / "qwen" / "rendered_answer.md").exists()
