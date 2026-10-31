from types import SimpleNamespace

import pytest

from sec_agent.agent_runtime.harness_usage import WireUsage


def messages(**usage):
    meter = WireUsage("deepseek_messages")
    meter.observe({"type": "message_start", "message": {"id": "r1", "usage": usage}})
    meter.observe({"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 20}})
    meter.observe({"type": "message_stop"})
    return meter


def test_messages_split_usage_and_cache_not_subtracted_twice():
    meter = messages(input_tokens=75, cache_read_input_tokens=25)
    usage = meter.reported()
    assert (usage.input_uncached, usage.input_cached, usage.output) == (75, 25, 20)
    assert usage.cost_micros(SimpleNamespace(input_miss=1_000_000, input_hit=100_000, output=2_000_000)) == 118
    assert meter.receipt()["raw_usage"]["input_tokens"] == 75


def test_chat_total_includes_cache_and_reasoning_is_not_extra_output():
    meter = WireUsage("qwen_chat")
    meter.observe({"id": "r2", "choices": [{"finish_reason": "tool_calls"}]})
    usage = {"prompt_tokens": 100, "completion_tokens": 20, "prompt_tokens_details": {"cached_tokens": 25}, "completion_tokens_details": {"reasoning_tokens": 5}}
    for _ in range(2):
        meter.observe({"id": "r2", "usage": usage})
    assert meter.reported() is None
    meter.done()
    assert vars(meter.reported()) == {"input_uncached": 75, "input_cached": 25, "input_cache_write": 0, "output": 20, "reasoning": 5}


@pytest.mark.parametrize("usage", [{}, {"input_tokens": True}, {"input_tokens": -1}, {"input_tokens": "75"}])
def test_missing_or_invalid_usage_never_becomes_free(usage):
    assert messages(**usage).reported() is None


def test_cancel_and_failed_stream_preserve_raw_counts_as_unknown():
    meter = messages(input_tokens=75)
    meter.terminal = False
    assert meter.reported() is None
    meter.observe({"type": "error", "error": {"type": "overloaded_error"}})
    meter.observe({"type": "message_stop"})
    assert meter.reported() is None
    assert meter.receipt()["raw_usage"] == {"input_tokens": 75, "output_tokens": 20}


def test_cache_write_needs_a_price_and_truncation_still_costs_money():
    meter = messages(input_tokens=75, cache_creation_input_tokens=10)
    meter.finish_reason = "max_tokens"
    assert meter.reported().cost_micros(SimpleNamespace()) is None
    assert meter.receipt()["finish_reason"] == "max_tokens"


def test_impossible_chat_cache_is_unknown():
    meter = WireUsage("qwen_chat")
    meter.observe({"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "prompt_tokens_details": {"cached_tokens": 11}}})
    meter.done()
    assert meter.reported() is None
