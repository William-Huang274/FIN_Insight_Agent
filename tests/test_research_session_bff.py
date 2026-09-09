"""New-task entry must select the native parent, never an archived report."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from apps.workbench.backend.api.v1.report_sessions import (
    ReportSessionService, build_report_sessions_router, public_event, public_state, public_native_failures, GRAPH, RESEARCH_GRAPH,
)
from sec_agent.agent_runtime.research_session_runtime import load_research_runtime_profile, research_session_graph


def test_native_failure_shows_reason_but_never_raw_error_payload():
    run = {"run_id": "latest-run", "updated_at": "2026-09-09T00:00:00Z"}
    events = public_native_failures({"tasks": [{"name": "research", "error":
        'ValueError("research_bundle_invalid_citations:wave2:PRIVATE_SECRET:/host/private/path")'}]}, run)
    assert events[0]["error_type"] == "ValueError"
    assert "research_bundle_invalid_citations" in events[0]["objective"]
    assert "引用校验" in events[0]["objective"]
    assert "PRIVATE" not in json.dumps(events) and "/host" not in json.dumps(events)
    provider = public_native_failures({"tasks": [{"name": "writer", "error":
        'AuthenticationError("Bearer SECRET /private/path")'}]}, run)
    assert provider[0]["error_type"] == "NativeNodeError" and "SECRET" not in json.dumps(provider)


def _app(*, enabled=True, graph_id=RESEARCH_GRAPH):
    calls = []
    thread_id, run_id = str(uuid4()), str(uuid4())
    thread = {"thread_id": thread_id, "status": "interrupted", "metadata": {"surface": "dell_report_workbench", "graph": graph_id}}
    async def create_thread(**kwargs):
        calls.append(("thread", kwargs))
        thread["metadata"] = kwargs["metadata"]
        return thread
    async def create_run(*args, **kwargs):
        calls.append(("run", args, kwargs))
        return {"run_id": run_id, "status": "pending"}
    async def get_thread(_):
        return thread
    async def get_state(_):
        return {"values": {"phase": "ready_for_human_review"}, "interrupts": [{"value": {"kind": "dell_report_review"}}]}
    service = ReportSessionService("http://127.0.0.1:18165", object(), sdk=SimpleNamespace(
        threads=SimpleNamespace(create=create_thread, get=get_thread, get_state=get_state), runs=SimpleNamespace(create=create_run)),
        research_profile={"default_question": "A new bounded Dell growth-quality research question", "title": "New Dell research"} if enabled else None)
    app = FastAPI()
    app.include_router(build_report_sessions_router(service), prefix="/api/v1")
    return app, service, calls, thread_id


def test_cumulative_usage_includes_native_run_pages_and_preserves_unknown_cache(tmp_path):
    app, service, _, tid = _app()
    service.audit_root = tmp_path
    rows = [{"run_id": str(uuid4()), "status": "success", "created_at": "2026-09-07T00:00:00Z",
        "updated_at": "2026-09-07T00:00:01Z", "metadata": {"model_calls_requested": 0}} for _ in range(101)]
    rows[-2]["metadata"] = {}  # no audit and no explicit zero-model action
    rows[-1]["metadata"] = {"human_action": "ask"}
    path = tmp_path / tid / rows[-1]["run_id"] / "model-call-events.jsonl"
    path.parent.mkdir(parents=True)
    events = [{"event": "started", "actor": "quick_writer", "call_id": "last-page-call", "model": "deepseek-v4-flash", "recorded_at": "2026-09-07T00:00:00Z"},
        {"event": "outcome", "actor": "quick_writer", "call_id": "last-page-call", "model": "deepseek-v4-flash",
         "input_tokens": 123, "output_tokens": 7, "total_tokens": 130, "elapsed_ms": 321.75, "usage_reported": True,
         "recorded_at": "2026-09-07T00:00:01Z"}]
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    offsets = []
    async def runs(_, *, limit, offset=0):
        offsets.append(offset)
        return rows[offset:offset+limit]
    service.sdk.runs.list = runs
    with TestClient(app) as client:
        response = client.get(f"/api/v1/research-sessions/{tid}")
        assert response.status_code == 200
        body = response.json()
    assert offsets == [0, 100] and len(body["runs"]) == 101
    total = body["cumulative_usage"]
    assert total["native_runs"] == 101 and total["input_tokens"] == 123 and total["total_tokens"] == 130
    assert total["recorded_requests"] == 1 and total["unknown_or_pending_requests"] == 0
    assert total["unknown_cache_requests"] == 1 and total["unpriced_requests"] == 1
    assert total["missing_audit_runs"] == 1 and total["elapsed_ms"] == 321.75
    assert total["unknown_elapsed_requests"] == 0
    assert body["runs"][-1]["elapsed_ms"] == 1000
    asyncio.run(service.http.aclose())


def test_new_task_and_review_remain_different_native_entries_and_fresh_has_no_seed():
    app, service, calls, _ = _app()
    with TestClient(app) as client:
        assert client.get("/api/v1/research-session-config").json()["fresh_research_enabled"]
        result = client.post("/api/v1/research-sessions", json={"mode": "research", "question": "A different actual user question about Dell growth quality"}, headers={"x-workbench-request": "1"})
        assert result.status_code == 200
        assert calls[-1][1][1] == RESEARCH_GRAPH
        payload = calls[-1][2]["input"]
        assert set(payload) == {"case_profile", "question"} and payload["question"].startswith("A different")
        assert calls[-1][2]["multitask_strategy"] == "reject"
        result = client.post("/api/v1/research-sessions", json={"mode": "review"}, headers={"x-workbench-request": "1"})
        assert result.status_code == 200 and calls[-1][1][1] == GRAPH and calls[-1][2]["input"] == {"open": True}
    asyncio.run(service.http.aclose())


def test_fresh_task_without_any_legacy_bundle_and_legacy_open_is_explicitly_unavailable():
    app, service, calls, _ = _app()
    service.artifacts = None
    with TestClient(app) as client:
        config = client.get("/api/v1/research-session-config").json()
        assert config["fresh_research_enabled"] and not config["legacy_review_enabled"]
        assert client.post("/api/v1/research-sessions", json={"mode": "review"}, headers={"x-workbench-request": "1"}).status_code == 409
        assert not calls
        assert client.post("/api/v1/research-sessions", json={"mode": "research"}, headers={"x-workbench-request": "1"}).status_code == 200
        assert calls[-1][1][1] == RESEARCH_GRAPH and "report" not in calls[-1][2]["input"]
    asyncio.run(service.http.aclose())


def test_disabled_fresh_does_not_fallback_or_create_orphan_and_rejects_host_controls():
    app, service, calls, _ = _app(enabled=False)
    with TestClient(app) as client:
        result = client.post("/api/v1/research-sessions", json={"mode": "research"}, headers={"x-workbench-request": "1"})
        assert result.status_code == 503 and not calls
        for body in ({"graph": "arbitrary"}, {"seed_path": "D:/private"}, {"mode": "research", "question": " " * 20}, {"node_budgets": {}}):
            assert client.post("/api/v1/research-sessions", json=body, headers={"x-workbench-request": "1"}).status_code == 422
        assert not calls
    asyncio.run(service.http.aclose())


@pytest.mark.parametrize("graph_id", [GRAPH, RESEARCH_GRAPH])
def test_followup_uses_owned_session_graph_not_legacy_constant(graph_id):
    app, service, calls, thread_id = _app(graph_id=graph_id)
    with TestClient(app) as client:
        result = client.post(f"/api/v1/research-sessions/{thread_id}/actions", json={"action": "ask", "message": "Explain the source"},
                             headers={"x-workbench-request": "1"})
        assert result.status_code == 200 and calls[-1][1][1] == graph_id
        assert "command" in calls[-1][2] and "input" not in calls[-1][2]
    asyncio.run(service.http.aclose())


def test_chart_only_sources_are_readable_only_inside_their_own_session():
    app, service, calls, thread_id = _app()
    ref = "PASSAGE::WEB::chart-only"
    async def state(_):
        return {"values": {"report": {"charts": [{"title": "Observed chart", "points": [
            {"source_id": ref, "label": "Current quarter", "series": "Revenue", "value": 10,
             "provenance": {"source_id": ref, "quote": "Revenue was 10 million", "literal": "10",
                "value_decimal": "10", "source_provenance": {"title": "Issuer disclosure", "source_url": "https://example.com/issuer",
                    "numeric_fact_authority": False}}}]}]}}}
    service.sdk.threads.get_state = state
    with TestClient(app) as client:
        response = client.get(f"/api/v1/research-sessions/{thread_id}/source", params={"source_id": ref})
        assert response.status_code == 200
        assert "Revenue was 10 million" in response.json()["text"]
        assert response.json()["source_url"] == "https://example.com/issuer"
        assert response.json()["numeric_fact_authority"] is False
        assert client.get(f"/api/v1/research-sessions/{thread_id}/source", params={"source_id": "PASSAGE::WEB::not-in-this-task"}).status_code == 404
    asyncio.run(service.http.aclose())


def test_public_task_projection_has_real_objective_and_dependencies_not_private_history():
    event = public_event({"kind": "task", "task_id": "T2", "actor": "finance", "event": "started", "objective": "Compare margins",
        "dependency_ids": ["T1"], "messages": [{"secret": "no"}], "reasoning_content": "private", "path": "D:/private"})
    assert event["dependency_ids"] == ["T1"] and "messages" not in event and "path" not in event
    projected = public_state({"values": {"question": "Research question", "case_papers": [{"notebook": "private source data"}],
        "research_tasks": [{"task_id": "T2", "objective": "Compare margins", "dependency_ids": ["T1"], "owner_role": "finance",
                            "hidden_reasoning": "private"}], "research_outcomes": [{"task_id": "T2", "status": "submitted"}]}})
    assert projected["research_tasks"][0]["status"] == "submitted"
    assert "case_papers" not in projected and "hidden_reasoning" not in str(projected)
    routed = public_event({"kind": "stage", "actor": "responsibility_router", "event": "handoff",
        "correction_round": 1, "responsible_paper_ids": ["P02", "D:/private"], "messages": ["private"]})
    assert routed["responsible_paper_ids"] == ["P02"] and routed["correction_round"] == 1 and "messages" not in routed
    history = public_state({"values": {"convergence_history": [{"actor": "synthesis", "correction_round": 0,
        "output": {"do_not_dump": "private trace"}}]}})
    assert history["responsibility_history"] == [{"actor": "synthesis", "correction_round": 0}]


def test_failed_workpaper_projects_only_deliverable_and_validation_metadata():
    projected = public_state({"values": {"research_failed_workpapers": [{"run_id": "run-a", "task_id": "task-a",
        "agent_state": {"review_reason": "model_turn_ceiling_reached_no_silent_completion",
            "notebook": {"model_turn_count": 2, "tool_action_count": 1,
                "observations": [{"raw_source": "private payload"}], "messages": ["private reasoning"]},
            "last_submission_attempt": {"arguments": {"narrative_markdown": "## Candidate\n\nObserved result.",
                "context_digest": "private binding", "hidden_reasoning": "private reasoning"},
                "feedback": [{"code": "specialist_tool_arguments_invalid", "message": "private raw error"}],
                "validation_issues": [{"location": ["claims", 1], "type": "value_error", "message": "invalid authority"}]}}}]}})
    failure = projected["research_failures"][0]
    assert failure["candidate"] == {"narrative_markdown": "## Candidate\n\nObserved result."}
    assert failure["saved_observations"] == 1 and failure["accepted"] is False
    assert failure["feedback_codes"] == ["specialist_tool_arguments_invalid"]
    assert failure["validation_issues"][0]["location"] == ["claims", 1]
    assert "private" not in str(projected)


def test_incomplete_review_output_and_host_notice_are_separate_public_records():
    projected = public_state({"values": {"case_review": {"source_run_id": "review-run",
        "counter": {"status": "incomplete_no_submission", "review": None,
            "incomplete_output": ["A source-backed public observation."],
            "runtime_notices": ["Model call limit reached"], "model_calls": 24,
            "tool_calls": 40, "messages": ["private reasoning"], "tool_feedback": ["private tool context"]}}}})
    failure = projected["research_failures"][0]
    assert failure["run_id"] == "review-run" and failure["task_id"] == "反证审查"
    assert failure["candidate"] == {"narrative_markdown": "A source-backed public observation."}
    assert failure["model_explanation"] is None
    assert failure["feedback_codes"] == ["Model call limit reached"]
    assert failure["accepted"] is False and failure["model_turns"] == 24
    assert "private" not in str(projected)


def test_failed_task_without_submission_keeps_tool_error_and_explicit_model_handoff_reason():
    state = {"values": {"research_failed_workpapers": [{"run_id": "r", "task_id": "t", "agent_state": {
        "review_reason": "source_read_failed", "notebook": {
            "feedback": [{"code": "source_read_failed", "message": "private source payload"}],
            "model_turn_records": [{"action": {"action": "request_human_review", "reason_summary": "原文读取未完成，请核对来源访问。",
                "reasoning_content": "private reasoning"}}]}}}]}}
    row = public_state(state)["research_failures"][0]
    assert row["candidate"] == {} and row["feedback_codes"] == ["source_read_failed"]
    assert row["model_explanation"] == "原文读取未完成，请核对来源访问。"
    assert "private" not in str(row)


def test_original_workpaper_reviews_are_visible_without_private_messages_or_raw_source_payloads():
    projected = public_state({"values": {"case_review": {"counter": {"messages": ["private trace"], "review": {
        "summary": "A current-period comparison needs revision.", "findings": [{"finding_id": "F1", "paper_id": "P09",
            "severity": "material", "diagnosis": "An old forecast is not a current actual.", "requested_change": "Compare actuals.",
            "problematic_quote": "Growth is capped", "source_checks": [{"raw": "do not dump"}], "messages": ["private"]}]}}}}})
    assert projected["workpaper_reviews"][0]["findings"][0]["paper_id"] == "P09"
    assert "private" not in json.dumps(projected) and "do not dump" not in json.dumps(projected)
    assert "report_review" not in projected  # intermediate findings are not a final review


def test_native_parent_schema_needs_no_credentials_or_archived_answer_and_role_budgets_are_valid():
    root = Path(__file__).resolve().parents[1]
    profile, case = load_research_runtime_profile(root)
    assert len(case["branch_topics"]) == 9 and profile["nodes"]["lead"]["profile"]["model"] == "deepseek-v4-flash"
    assert profile["nodes"]["specialist"]["profile"]["model"] == "deepseek-v4-pro"
    async def exercise():
        async with research_session_graph({}, SimpleNamespace(execution_runtime=None)) as graph:
            schema = graph.get_input_jsonschema()
            assert set(schema["properties"]) == {"case_profile", "question"}
            assert {"research", "case_review", "convergence", "human_review", "research_revision"}.issubset(graph.nodes)
    asyncio.run(exercise())


def test_direct_passage_and_calculation_operand_sources_remain_session_bound_and_paginated():
    app, service, _, thread_id = _app()
    sources = [{"source_id": "PASSAGE::current", "text": "A" * 17000,
                "source_url": "https://example.com/current", "numeric_fact_authority": False},
               {"source_id": "evidence-from-calculator", "text": "Exact reviewed source operand",
                "source_url": "https://example.com/operand", "numeric_fact_authority": False}]
    async def state(_):
        return {"values": {"synthesis": {"citations": {"PASSAGE::current": {"sources": [sources[0]]}}},
            "report": {"citations": {"CALC::current": {"sources": [sources[1]]}}}}}
    service.sdk.threads.get_state = state
    with TestClient(app) as client:
        path = f"/api/v1/research-sessions/{thread_id}/source"
        result = client.get(path, params={"source_id": "PASSAGE::current"})
        assert result.status_code == 200 and len(result.json()["text"]) == 16000
        assert result.json()["next_offset"] == 16000 and not result.json()["numeric_fact_authority"]
        last = client.get(path, params={"source_id": "PASSAGE::current", "offset": 16000}).json()
        assert last["text"] == "A" * 1000 and last["next_offset"] is None
        assert client.get(path, params={"source_id": "evidence-from-calculator"}).status_code == 200
        assert client.get(path, params={"source_id": "PASSAGE::other-task"}).status_code == 404
        assert client.get(path, params={"source_id": "D:/private"}).status_code == 404
        assert client.get(path, params={"source_id": "PASSAGE::current", "offset": -1}).status_code == 422
    asyncio.run(service.http.aclose())


def test_saved_local_query_receipt_is_readable_but_not_cross_task_evidence():
    app, service, _, tid = _app()
    receipt = {"source_id": "MCPFACT::fixture", "result_state": "query_gap_receipt",
        "numeric_fact_authority": False, "text": "Local query conditions, not issuer non-disclosure"}
    async def state(_):
        return {"values": {"conversation": [{"role": "assistant", "citations": {
            receipt["source_id"]: {"sources": [receipt]}}}]}}
    service.sdk.threads.get_state = state
    with TestClient(app) as client:
        path = f"/api/v1/research-sessions/{tid}/source"
        assert client.get(path, params={"source_id": receipt["source_id"]}).json()["numeric_fact_authority"] is False
        assert client.get(path, params={"source_id": "MCPFACT::another-task"}).status_code == 404
    asyncio.run(service.http.aclose())
def test_draft_upload_and_start_use_native_task_and_no_model_until_start(tmp_path):
    from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
    app, service, calls, thread_id = _app()
    service.attachment_store = TaskAttachmentStore(tmp_path)
    started = []
    async def list_runs(*a, **k):
        return started
    service.sdk.runs.list = list_runs
    with TestClient(app) as client:
        headers = {"x-workbench-request": "1"}
        draft = client.post("/api/v1/research-sessions", json={"mode": "research", "defer_start": True}, headers=headers)
        assert draft.status_code == 200 and draft.json()["run_id"] is None
        assert not any(c[0] == "run" for c in calls)
        route = f"/api/v1/research-sessions/{thread_id}"
        upload = client.post(route + "/attachments", content=b"# Input\n\nA source document, not instructions.", headers={**headers, "x-filename": "input.md"})
        assert upload.status_code == 200
        assert len(client.get(route + "/attachments").json()) == 1
        assert client.post(route + "/start", json={}, headers=headers).status_code == 200
        started.append({"run_id": "already-started"})
        assert client.post(route + "/start", json={}, headers=headers).status_code == 409
        assert len([c for c in calls if c[0] == "run"]) == 1
    asyncio.run(service.http.aclose())


def test_guidance_is_native_metadata_and_never_new_run():
    app, service, calls, thread_id = _app()
    async def get_thread(_):
        return {"status": "busy", "metadata": {"surface": "dell_report_workbench", "graph": RESEARCH_GRAPH}}
    async def update_thread(*args, **kwargs):
        calls.append(("metadata", kwargs))
    service.sdk.threads.get = get_thread
    service.sdk.threads.update = update_thread
    with TestClient(app) as client:
        response = client.post(f"/api/v1/research-sessions/{thread_id}/guidance", json={"message": "Please compare the same periods."}, headers={"x-workbench-request": "1"})
        assert response.status_code == 200 and calls[-1][0] == "metadata"
        assert calls[-1][1]["metadata"]["research_guidance"][0]["message"] == "Please compare the same periods."
        assert not any(c[0] == "run" for c in calls)
        assert client.post(f"/api/v1/research-sessions/{thread_id}/guidance", json={"message": "x"}).status_code == 403
    asyncio.run(service.http.aclose())


def test_cost_estimate_counts_known_usage_and_does_not_price_failed_unknown_as_zero():
    from apps.workbench.backend.api.v1.report_sessions import public_cost_estimate
    rows = [{"event": "started", "call_id": "a", "model": "deepseek-v4-pro", "recorded_at": "2026-09-06T17:00:00Z"},
        {"event": "outcome", "call_id": "a", "cache_hit_tokens": 1000, "cache_miss_tokens": 2000, "output_tokens": 100},
        {"event": "started", "call_id": "b", "model": "deepseek-v4-pro", "recorded_at": "2026-09-06T17:00:00Z"},
        {"event": "outcome", "call_id": "b", "error_type": "OpenAIConnectionError"},
        {"kind": "task", "event": "outcome", "task_id": "T1", "status": "needs_attention"}]
    estimate = public_cost_estimate(rows)
    assert estimate["known_cny"] == pytest.approx(0.0105)
    assert estimate["priced_requests"] == 1 and estimate["unknown_or_pending_requests"] == 1
    rows.append({"event": "outcome", "call_id": "preflight", "provider_call_attempted": False,
                 "status": "blocked_before_transport_input_limit"})
    corrected = public_cost_estimate(rows)
    assert corrected["not_attempted_requests"] == 1
    assert corrected["unknown_or_pending_requests"] == 1 and corrected["known_cny"] == estimate["known_cny"]


def test_continue_remaining_uses_native_interrupt_and_no_browser_seed_or_checkpoint_update():
    app, service, calls, thread_id = _app()
    async def get_state(_):
        return {"values": {"phase": "research_needs_attention", "case_papers": [{"private_not_returned": True}]},
                "interrupts": [{"value": {"kind": "research_needs_attention"}}]}
    service.sdk.threads.get_state = get_state
    with TestClient(app) as client:
        route = f"/api/v1/research-sessions/{thread_id}/continue-remaining"
        assert client.post(route).status_code == 403
        result = client.post(route, headers={"x-workbench-request": "1"})
        assert result.status_code == 200
        assert calls[-1][2]["command"] == {"resume": {"action": "continue_remaining"}}
        assert "input" not in calls[-1][2] and "checkpoint" not in calls[-1][2]
        assert calls[-1][2]["metadata"]["human_action"] == "continue_remaining"
        async def after_review(_):
            return {"values": {"phase": "research_needs_attention", "case_papers": [1], "case_review": {"counter": {}}},
                    "interrupts": [{"value": {"kind": "research_needs_attention"}}]}
        service.sdk.threads.get_state = after_review
        assert client.post(route, headers={"x-workbench-request": "1"}).status_code == 409
    asyncio.run(service.http.aclose())


@pytest.mark.parametrize("node", ["remaining_research", "convergence"])
def test_known_remaining_failure_restarts_native_pending_node_but_unknown_usage_is_blocked(tmp_path, node):
    app, service, calls, thread_id = _app()
    run_id = str(uuid4())
    service.audit_root = tmp_path
    async def thread(_):
        return {"status": "error", "metadata": {"surface": "dell_report_workbench", "graph": RESEARCH_GRAPH}}
    async def state(_):
        values = {"phase": "research_needs_attention", "case_papers": [{}]}
        if node == "convergence":
            values.update(phase="research_writing", case_review={"counter": {"status": "review_submitted"}})
        return {"values": values,
                "tasks": [{"name": node, "error": "known_local_submission_failure"}]}
    async def runs(*args, **kwargs):
        return [{"run_id": run_id, "status": "error", "metadata": {"human_action": "continue_remaining"}}]
    service.sdk.threads.get, service.sdk.threads.get_state, service.sdk.runs.list = thread, state, runs
    folder = tmp_path / thread_id / run_id
    folder.mkdir(parents=True)
    path = folder / "model-call-events.jsonl"
    events = [{"call_id": "failed", "event": "started"},
              {"call_id": "failed", "event": "outcome", "status": "provider_output_truncated", "total_tokens": 20}]
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    with TestClient(app) as client:
        route = f"/api/v1/research-sessions/{thread_id}/continue-remaining"
        assert client.post(route, headers={"x-workbench-request": "1"}).status_code == 200
        assert calls[-1][2]["input"] is None and "command" not in calls[-1][2] and "checkpoint" not in calls[-1][2]
        path.write_text(json.dumps(events[0]), encoding="utf-8")
        assert client.post(route, headers={"x-workbench-request": "1"}).status_code == 409
    asyncio.run(service.http.aclose())
