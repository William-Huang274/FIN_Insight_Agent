from __future__ import annotations

import sqlite3

from sec_agent.r53_r60_runtime_task_spine import FinSightResearchRuntimeFacade
from sec_agent.r53_r60_tool_sandbox_spine import (
    FinSightToolGateway,
    build_s2_gate,
    record_approval_decision,
)


def test_tool_gateway_allows_and_ledgers_safe_tool_call(tmp_path):
    runtime = FinSightResearchRuntimeFacade(tmp_path / "runtime.sqlite")
    task = runtime.create_task("S2 allowed tool call", task_id="task_s2_allowed")
    task_id = task["task"]["task_id"]
    runtime.store.transition_task(task_id, "running", actor="research_lead", progress=10)
    gateway = FinSightToolGateway(runtime, workspace_root=tmp_path)

    decision = gateway.invoke_tool(
        task_id,
        actor_id="research_lead",
        node="lead_review_checkpoint",
        tool_id="database_query",
        arguments={"query": "select * from gold_fact_signal_mart where ticker='NVDA'", "limit": 5},
    )

    state = runtime.get_task_state(task_id)
    assert decision.status == "executed"
    assert decision.policy_decision == "allow"
    assert decision.artifact_ref_ids
    assert state["progress_projection"]["artifact_count"] == 1
    assert state["progress_projection"]["trace_span_count"] == 1

    with sqlite3.connect(tmp_path / "runtime.sqlite") as conn:
        row = conn.execute("select status, policy_decision from tool_invocations where tool_call_id = ?", (decision.tool_call_id,)).fetchone()
    assert row == ("executed", "allow")


def test_tool_gateway_blocks_writer_web_path_escape_secret_and_unknown_tool(tmp_path):
    runtime = FinSightResearchRuntimeFacade(tmp_path / "runtime.sqlite")
    task = runtime.create_task("S2 blocked tool calls", task_id="task_s2_blocked")
    task_id = task["task"]["task_id"]
    runtime.store.transition_task(task_id, "running", actor="research_lead", progress=10)
    gateway = FinSightToolGateway(runtime, workspace_root=tmp_path)

    decisions = [
        gateway.invoke_tool(
            task_id,
            actor_id="memo_writer",
            node="memo_writer",
            tool_id="live_web_snapshot",
            arguments={"url": "https://nvidia.com/en-us/data-center/"},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="research_lead",
            node="lead_review_checkpoint",
            tool_id="live_web_snapshot",
            arguments={"url": "https://untrusted.example.com/promo"},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="input_parser",
            node="input_parser",
            tool_id="document_parser",
            arguments={"input_path": "..\\outside.pdf"},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="research_lead",
            node="lead_review_checkpoint",
            tool_id="database_query",
            arguments={"query": "select 1", "api_key": "must-not-persist"},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="research_lead",
            node="lead_review_checkpoint",
            tool_id="unknown_tool",
            arguments={"query": "x"},
        ),
    ]

    reasons = {decision.blocked_reason for decision in decisions}
    assert reasons == {
        "actor_tool_not_allowed",
        "domain_not_allowlisted",
        "path_outside_allowed_roots",
        "credential_argument_forbidden",
        "unknown_tool",
    }
    assert all(decision.status == "blocked" for decision in decisions)

    with sqlite3.connect(tmp_path / "runtime.sqlite") as conn:
        payloads = [row[0] for row in conn.execute("select payload_json from tool_invocations").fetchall()]
    assert "must-not-persist" not in "\n".join(payloads)
    assert "[REDACTED]" in "\n".join(payloads)


def test_tool_gateway_records_pre_and_post_approval_attempts_separately(tmp_path):
    runtime = FinSightResearchRuntimeFacade(tmp_path / "runtime.sqlite")
    task = runtime.create_task("S2 approval tool call", task_id="task_s2_approval")
    task_id = task["task"]["task_id"]
    runtime.store.transition_task(task_id, "running", actor="research_lead", progress=10)
    gateway = FinSightToolGateway(runtime, workspace_root=tmp_path)

    blocked = gateway.invoke_tool(
        task_id,
        actor_id="research_lead",
        node="lead_review_checkpoint",
        tool_id="python_analysis",
        arguments={"workspace_path": ".tmp\\analysis.py"},
    )
    approval = record_approval_decision(
        runtime.store,
        task_id,
        actor_id="research_lead",
        tool_id="python_analysis",
        decision="approved",
        approver_actor_id="human_reviewer",
        reason="unit test approval",
    )
    allowed = gateway.invoke_tool(
        task_id,
        actor_id="research_lead",
        node="lead_review_checkpoint",
        tool_id="python_analysis",
        arguments={"workspace_path": ".tmp\\analysis.py"},
        approval_decision=approval,
    )

    assert blocked.status == "blocked"
    assert blocked.blocked_reason == "human_approval_required"
    assert allowed.status == "executed"
    assert blocked.tool_call_id != allowed.tool_call_id

    with sqlite3.connect(tmp_path / "runtime.sqlite") as conn:
        count = conn.execute("select count(*) from tool_invocations where tool_id = 'python_analysis'").fetchone()[0]
    assert count == 2


def test_build_s2_gate_outputs_l4_scope_pass(tmp_path):
    summary = build_s2_gate(tmp_path)

    assert summary["release_decision"] == "S2_L4_scope_pass"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["counts"]["tool_invocations"] == 9
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()
