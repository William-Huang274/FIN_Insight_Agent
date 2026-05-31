from __future__ import annotations

import json
from pathlib import Path

from sec_agent.workbench import inspect_run_artifacts
from sec_agent.workbench.jobs import new_saved_run_inspection_job


def test_inspect_run_artifacts_summarizes_saved_run(tmp_path: Path) -> None:
    run_dir = _write_saved_run_fixture(tmp_path)

    index = inspect_run_artifacts(run_dir)

    assert index.status == "pass"
    assert index.state_summary["run_id"] == "fixture_run"
    assert index.state_summary["stage_count"] == 1
    assert index.gate_summary["true_gate_count"] == 1
    assert "SEC Agent Answer" in index.answer_preview
    by_id = {artifact.artifact_id: artifact for artifact in index.artifacts}
    assert by_id["exact_value_ledger"].summary["row_count"] == 1
    assert by_id["agent_outputs"].summary["row_count"] == 1
    assert by_id["query_contract"].summary["source_policy"] == "SEC_PRIMARY_MIXED_RECENT"


def test_inspect_run_artifacts_warns_when_required_state_is_missing(tmp_path: Path) -> None:
    (tmp_path / "qwen").mkdir()
    (tmp_path / "qwen" / "rendered_answer.md").write_text("answer", encoding="utf-8")

    index = inspect_run_artifacts(tmp_path)

    assert index.status == "warn"
    assert index.missing_required == ["graph_state"]
    assert "graph_state: missing" in index.warnings


def test_inspect_run_artifacts_accepts_native_checkpoint_without_legacy_state(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "langgraph_node_checkpoints.json",
        {
            "run_id": "native_fixture",
            "status": "completed",
            "checkpoint_count": 3,
            "latest_completed_node": "persist_session_state",
        },
    )
    _write_json(
        tmp_path / "langgraph_native_summary.json",
        {
            "run_id": "native_fixture",
            "status": "completed",
            "state_summary": {"status": "completed", "context_row_count": 2},
            "node_checkpoints": [{"node": "load_session_state"}, {"node": "persist_session_state"}],
        },
    )

    index = inspect_run_artifacts(tmp_path)

    assert index.status == "pass"
    assert index.missing_required == []
    assert index.warnings == []
    assert index.state_summary["run_id"] == "native_fixture"
    assert index.state_summary["node_count"] == 2


def test_inspect_run_artifacts_summarizes_multi_agent_trace(tmp_path: Path) -> None:
    run_dir = _write_saved_run_fixture(tmp_path)
    _write_json(
        run_dir / "multi_agent_summary.json",
        {
            "schema_version": "sec_agent_multi_agent_summary_v0.1",
            "run_id": "fixture_run",
            "status": "completed",
            "execution_mode": "standard_memo",
            "activated_agents": ["research_lead", "sec_operator", "memo_writer", "verifier", "renderer"],
            "skipped_agents": [{"agent_id": "universe_relationship", "reason": "Not needed."}],
            "tool_call_count": 2,
            "tool_calls": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "row_count": 3, "source_gap_count": 0}
            ],
            "second_pass": {"attempts": 1, "result": {"added_row_count": 0}},
            "loop_break_reason": "no_incremental_evidence",
            "bounded_answer_allowed": True,
        },
    )

    index = inspect_run_artifacts(run_dir)
    by_id = {artifact.artifact_id: artifact for artifact in index.artifacts}

    assert by_id["multi_agent_summary"].exists is True
    assert by_id["multi_agent_summary"].summary["execution_mode"] == "standard_memo"
    assert by_id["multi_agent_summary"].summary["tool_call_count"] == 2
    assert by_id["multi_agent_summary"].summary["second_pass_attempts"] == 1
    assert index.state_summary["multi_agent"]["loop_break_reason"] == "no_incremental_evidence"


def test_run_job_records_artifact_status(tmp_path: Path) -> None:
    index = inspect_run_artifacts(_write_saved_run_fixture(tmp_path))

    job = new_saved_run_inspection_job(run_dir=tmp_path, artifact_index=index, job_id="job_fixture", profile_id="profile_a")

    assert job.job_id == "job_fixture"
    assert job.job_type == "saved_run_inspection"
    assert job.status == "completed"
    assert job.profile_id == "profile_a"
    assert job.metadata["artifact_status"] == "pass"


def _write_saved_run_fixture(root: Path) -> Path:
    run_dir = root / "run"
    (run_dir / "qwen").mkdir(parents=True)
    (run_dir / "post_gates").mkdir()
    _write_json(
        run_dir / "sec_agent_state.json",
        {
            "run_id": "fixture_run",
            "status": "completed",
            "source_policy": "SEC_PRIMARY_MIXED_RECENT",
            "selected_tickers": ["NVDA"],
            "selected_years": [2025],
            "stages": [{"name": "render_answer", "status": "completed"}],
        },
    )
    _write_json(
        run_dir / "runtime_evidence_coverage_matrix.json",
        {"summary": {"coverage_complete": True, "context_row_count": 3, "ledger_row_count": 1}},
    )
    _write_json(run_dir / "query_contract.json", {"source_policy": "SEC_PRIMARY_MIXED_RECENT", "filing_types": ["10-K"]})
    _write_json(run_dir / "runtime_exact_value_ledger.json", {"rows": [{"metric_id": "m1"}]})
    _write_json(run_dir / "runtime_judgment_plan.json", {"plans": [{"driver": "growth"}]})
    _write_json(run_dir / "post_gates" / "sec_benchmark_post_gates_summary.json", {"answer_gate_pass": True})
    _write_json(run_dir / "run_performance.json", {"total_elapsed_ms": 1234, "stages": [{"name": "retrieve"}]})
    _write_jsonl(run_dir / "qwen" / "agent_outputs.jsonl", [{"status": "answered_api_model"}])
    (run_dir / "qwen" / "rendered_answer.md").write_text("# SEC Agent Answer\n\nfixture answer", encoding="utf-8")
    return run_dir


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
