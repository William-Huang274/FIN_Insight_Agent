import json

import pytest

from scripts.qualification.dell_q1_specialist_paid_shadow.audit_token_cost import (
    audit, audit_context_projection, cost_parts, message_components, peak_multiplier, usage_details, phase_for_actor,
)


@pytest.mark.parametrize("timestamp,expected", [
    ("2026-09-05T19:00:00Z", 1),  # Sunday Beijing
    ("2026-09-07T01:00:00Z", 2),
    ("2026-09-07T04:00:00Z", 1),
    ("2026-09-07T06:00:00Z", 2),
    ("2026-09-07T10:00:00Z", 1),
])
def test_peak_schedule(timestamp, expected):
    assert peak_multiplier(timestamp) == expected


def test_current_flash_scenario_is_third_of_pro_not_predicted_saving():
    args = (800, 200, 100, 1)
    pro = sum(cost_parts("deepseek-v4-pro", *args).values())
    flash = sum(cost_parts("deepseek-v4-flash", *args).values())
    assert pro == pytest.approx(3 * flash)


def test_report_never_serializes_private_text_or_invents_missing_usage(tmp_path):
    folder = tmp_path / "attempt"
    folder.mkdir()
    events = [
        {"kind": "task", "event": "started", "task_id": "T1"},
        {"kind": "task", "event": "outcome", "task_id": "T1", "status": "submitted"},
        {"event": "started", "call_id": "a", "actor": "specialist", "model": "deepseek-v4-pro",
         "recorded_at": "2026-09-05T19:00:00Z"},
        {"event": "outcome", "call_id": "a", "status": "success", "usage_reported": True,
         "input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
        {"event": "started", "call_id": "b", "actor": "specialist", "model": "deepseek-v4-pro",
         "recorded_at": "2026-09-05T19:01:00Z"},
        {"event": "outcome", "call_id": "b", "status": "provider_call_failed"},
        {"event": "outcome", "call_id": "c", "status": "blocked_before_transport_input_limit"},
    ]
    private = {"call_id": "a", "messages": [{"type": "ai", "content": "private-source-sentinel",
        "additional_kwargs": {"reasoning_content": "private-reasoning-sentinel"}}],
        "raw_response": {"usage_metadata": {"input_token_details": {"cache_read": 800},
                                             "output_token_details": {"reasoning": 70}}}}
    (folder / "model-call-events.jsonl").write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
    (folder / "model-context-reasoning.private.jsonl").write_text(json.dumps(private), encoding="utf-8")
    report = audit(tmp_path)
    assert report["totals"]["requests"] == 2
    assert report["totals"]["cache_miss_tokens"] == 200
    assert report["totals"]["cost_known_requests"] == 1
    assert len(report["not_sent_outcomes"]) == 1
    assert report["calls"][1]["modeled_cost_cny"] is None
    assert "sentinel" not in json.dumps(report)


def test_detail_unknown_is_not_reported_as_zero():
    assert usage_details({}) == (None, None)
    assert usage_details({"usage_metadata": {"input_token_details": {"cache_read": True}}}) == (None, None)


@pytest.mark.parametrize("actor,phase", [("context_summary:writer", "context_summary"),
    ("specialist:Q4:attempt", "research"), ("author_P02", "author_revision"),
    ("report_verifier", "review"), ("writer", "writing_or_answer"), ("synthesis", "synthesis")])
def test_cost_phase_is_descriptive_not_dropped_or_inferred_success(actor, phase):
    assert phase_for_actor(actor) == phase


def test_native_separate_request_and_response_preserve_context_attribution(tmp_path):
    folder = tmp_path / "native"
    folder.mkdir()
    events = [{"event": "started", "call_id": "a", "actor": "case_counter", "model": "deepseek-v4-pro",
        "recorded_at": "2026-09-06T01:00:00Z"}, {"event": "outcome", "call_id": "a",
        "status": "success", "usage_reported": True, "input_tokens": 10, "output_tokens": 5, "total_tokens": 15}]
    private = [{"event": "request", "call_id": "a", "messages": [{"type": "human", "content": "private sentinel"}]},
        {"event": "response", "call_id": "a", "raw_response": {"usage_metadata": {
            "input_token_details": {"cache_read": 8}, "output_token_details": {"reasoning": 3}}}}]
    (folder / "model-call-events.jsonl").write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
    (folder / "model-context-reasoning.private.jsonl").write_text("\n".join(map(json.dumps, private)), encoding="utf-8")
    result = audit(tmp_path)
    assert result["totals"]["message_content_characters"] == len("private sentinel")
    assert result["totals"]["cache_hit_tokens"] == 8
    assert "sentinel" not in json.dumps(result)


def test_component_sizes_are_characters_not_tokens():
    assert message_components([{"type": "ai", "content": "中文",
        "additional_kwargs": {"reasoning_content": "abc"}, "tool_calls": []}]) == {
            "ai_content": 2, "ai_reasoning": 3, "ai_tool_calls": 2}


def test_historical_projection_is_offline_non_mutating_and_never_discloses_text(tmp_path, monkeypatch):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
    monkeypatch.setattr(ReasoningPreservingChatDeepSeek, "_generate", lambda *a, **kw: pytest.fail("offline audit called provider"))
    folder = tmp_path / "attempt"
    folder.mkdir()
    messages = [HumanMessage(content="private question sentinel")]
    for i in range(3):
        messages += [AIMessage(content="", additional_kwargs={"reasoning_content": "private reasoning sentinel"}, tool_calls=[
            {"name": "read_source_document", "args": {"source_id": str(i)}, "id": str(i), "type": "tool_call"}]),
            ToolMessage(content="private source sentinel " * 500, name="read_source_document", tool_call_id=str(i),
                artifact={"text": "private artifact sentinel"})]
    record = {"event": "request", "call_id": "fixture", "actor": "writer",
              "messages": [m.model_dump(mode="json") for m in messages]}
    path = folder / "model-context-reasoning.private.jsonl"
    path.write_text(json.dumps(record) + "\n" + json.dumps({"event": "response", "call_id": "fixture"}), encoding="utf-8")
    original = path.read_bytes()
    report = audit_context_projection(tmp_path, trigger_tokens=1, keep=1)
    assert report["totals"]["requests"] == report["totals"]["requests_with_cleared_results"] == 1
    assert report["totals"]["wire_message_characters_after"] < report["totals"]["wire_message_characters_before"]
    assert report["totals"]["changed_tool_results"] == 2
    assert report["history_reasoning_tool_pairing_unchanged"] and report["new_provider_calls"] == 0
    assert report["quality_or_paid_cost_improvement_proven"] is False
    assert path.read_bytes() == original and "sentinel" not in json.dumps(report)
