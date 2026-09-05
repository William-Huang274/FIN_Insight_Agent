import json

import pytest

from scripts.qualification.dell_q1_specialist_paid_shadow.audit_token_cost import (
    audit, cost_parts, message_components, peak_multiplier, usage_details,
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


def test_component_sizes_are_characters_not_tokens():
    assert message_components([{"type": "ai", "content": "中文",
        "additional_kwargs": {"reasoning_content": "abc"}, "tool_calls": []}]) == {
            "ai_content": 2, "ai_reasoning": 3, "ai_tool_calls": 2}
