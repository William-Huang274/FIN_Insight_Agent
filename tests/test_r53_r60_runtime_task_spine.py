from __future__ import annotations

import sqlite3

import pytest

from sec_agent.r53_r60_runtime_task_spine import (
    FinSightResearchRuntimeFacade,
    IllegalStatusTransition,
    RuntimeTaskSpineStore,
    build_s1_gate,
)


def test_runtime_task_spine_create_transition_resume_replay(tmp_path):
    facade = FinSightResearchRuntimeFacade(tmp_path / "runtime.sqlite")

    state = facade.create_task(
        "Analyze NVDA product and capital readiness",
        task_id="task_runtime_spine_unit",
        trace_id="trace_runtime_spine_unit",
        objective={"required_dimensions": ["fundamental", "product"]},
    )
    task_id = state["task"]["task_id"]

    facade.store.transition_task(task_id, "running", actor="research_lead", progress=10)
    artifact = facade.record_artifact_ref(
        task_id,
        artifact_type="retrieval_plan",
        uri="inline://unit/retrieval_plan",
        payload={"routes": ["sql_exact", "graph"]},
    )
    node = facade.record_node_result(
        task_id,
        node="research_lead_objective_contract",
        status="pass",
        input_payload={"query": state["task"]["query_text"]},
        output_payload={"artifact_ref_id": artifact["artifact_ref_id"]},
        artifact_ref_ids=[artifact["artifact_ref_id"]],
    )
    facade.append_workpaper_event(
        task_id,
        actor="product_specialist",
        event_type="section_claim_added",
        section_id="product",
        payload={"claim": "product graph available"},
    )
    checkpoint = facade.save_checkpoint(
        task_id,
        checkpoint_kind="langgraph_node_checkpoint",
        checkpoint_uri="inline://unit/checkpoint",
        state_payload={"node": node["node"]},
        recoverable_node=node["node"],
    )
    facade.record_trace_span(
        task_id,
        span_kind="model_call",
        name="deterministic_node",
        status="pass",
        latency_ms=5,
        token_count=0,
        cost_amount=0.0,
    )
    facade.store.transition_task(task_id, "succeeded", actor="verifier", progress=100)

    with pytest.raises(IllegalStatusTransition):
        facade.store.transition_task(task_id, "running", actor="unit_test")

    facade.resume_task(task_id, actor="human_reviewer", checkpoint_ref_id=checkpoint["checkpoint_ref_id"])
    facade.store.transition_task(task_id, "running", actor="research_lead", progress=20)
    final_state = facade.store.transition_task(task_id, "succeeded", actor="verifier", progress=100)

    replay = facade.replay_task(task_id)
    assert final_state["task"]["status"] == "succeeded"
    assert replay["replay_status"] == "replayable"
    assert len(replay["runs"]) == 2
    assert replay["progress_projection"]["status"] == "succeeded"
    assert replay["progress_projection"]["event_count"] == len(replay["events"])
    assert replay["artifact_refs"][0]["artifact_type"] == "retrieval_plan"


def test_workpaper_event_append_only_triggers(tmp_path):
    facade = FinSightResearchRuntimeFacade(tmp_path / "runtime.sqlite")
    task = facade.create_task("Append-only ledger check", task_id="task_append_only")
    task_id = task["task"]["task_id"]
    event = facade.append_workpaper_event(
        task_id,
        actor="research_lead",
        event_type="section_added",
        section_id="summary",
        payload={"text": "initial section"},
    )

    with sqlite3.connect(tmp_path / "runtime.sqlite") as conn:
        with pytest.raises(sqlite3.DatabaseError, match="append_only_update_forbidden"):
            conn.execute(
                "update workpaper_events set actor = actor where workpaper_event_id = ?",
                (event["workpaper_event_id"],),
            )
        with pytest.raises(sqlite3.DatabaseError, match="append_only_delete_forbidden"):
            conn.execute(
                "delete from workpaper_events where workpaper_event_id = ?",
                (event["workpaper_event_id"],),
            )


def test_gateway_payload_import_and_worker_update(tmp_path):
    facade = FinSightResearchRuntimeFacade(tmp_path / "runtime.sqlite")
    state = facade.import_gateway_task(
        {
            "task_id": "gateway_unit_task",
            "trace_id": "trace_gateway_unit",
            "query": "Gateway compatibility task",
            "user_id": "gateway_user",
            "case_id": "gateway_case",
            "mode": "local_smoke",
            "metadata": {"origin": "java_gateway"},
        }
    )

    assert state["task"]["status"] == "pending"
    updated = facade.record_worker_update(
        "gateway_unit_task",
        {
            "status": "SUCCESS",
            "progress": 100,
            "memo": "Gateway compatibility succeeded",
            "evidence": [{"source_family": "runtime_bridge"}],
            "events": [{"stream": "worker", "message": "done"}],
        },
    )

    replay = facade.replay_task("gateway_unit_task")
    assert updated["task"]["status"] == "succeeded"
    assert updated["task"]["trace_id"] == "trace_gateway_unit"
    assert any(row["artifact_type"] == "gateway_worker_update_payload" for row in replay["artifact_refs"])
    assert any(row["event_type"] == "worker_event" for row in replay["events"])


def test_build_s1_gate_outputs_l4_scope_pass(tmp_path):
    summary = build_s1_gate(tmp_path)

    assert summary["release_decision"] == "S1_L4_scope_pass"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["counts"]["gate_count"] == 10
    assert summary["counts"]["gate_fail_count"] == 0
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()

    store = RuntimeTaskSpineStore(tmp_path / summary["outputs"]["sqlite_store"])
    assert store.table_counts()["research_tasks"] == 2
