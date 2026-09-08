from apps.workbench.backend.application.context_usage import request_context_usage


def test_context_is_last_request_per_actor_not_total_bill_and_pending_is_unknown():
    events = [
        {"kind": "model", "event": "started", "actor": "lead", "call_id": "1", "model": "deepseek-v4-flash", "recorded_at": "01"},
        {"kind": "model", "event": "outcome", "actor": "lead", "call_id": "1", "input_tokens": 100, "total_tokens": 120, "recorded_at": "02"},
        {"kind": "model", "event": "started", "actor": "lead", "call_id": "2", "model": "deepseek-v4-flash", "input_characters": 900, "recorded_at": "03"},
        {"kind": "model", "event": "outcome", "actor": "writer", "call_id": "3", "model": "deepseek-v4-pro", "input_tokens": 810000, "recorded_at": "04"},
    ]
    result = {n["actor"]: n for n in request_context_usage(events)["nodes"]}
    assert result["lead"]["input_tokens"] is None
    assert result["lead"]["input_characters"] == 900
    assert result["writer"]["input_tokens"] == 810000
    assert result["writer"]["near_capacity"]


def test_unknown_model_has_no_invented_capacity_and_negative_usage_is_unknown():
    result = request_context_usage([{"kind": "model", "call_id": "1", "actor": "a", "input_tokens": -1, "model": "other"}])["nodes"][0]
    assert result["input_tokens"] is None and result["capacity_tokens"] is None
    assert not result["near_capacity"]


def test_late_completion_cannot_replace_newer_pending_request():
    events = [
        {"kind": "model", "event": "started", "actor": "lead", "call_id": "old", "recorded_at": "01"},
        {"kind": "model", "event": "started", "actor": "lead", "call_id": "new", "recorded_at": "02"},
        {"kind": "model", "event": "outcome", "actor": "lead", "call_id": "old", "recorded_at": "03", "input_tokens": 500},
    ]
    latest = request_context_usage(events)["nodes"][0]
    assert latest["call_id"] == "new" and latest["input_tokens"] is None
