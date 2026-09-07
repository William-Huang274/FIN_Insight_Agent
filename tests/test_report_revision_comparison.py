import asyncio
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy

from langchain_core.messages import AIMessage
import pytest

from scripts.qualification.report_revision_comparison import ComparisonAudit, input_state, model_settings


def test_comparison_inputs_do_not_share_mutable_original_report_state():
    snapshot = {"state": {"question": "Synthetic question", "report": {"title": "Fixture",
        "narrative_markdown": "Fixture prose", "citations": {}}, "revisions": {}, "synthesis": {}}}
    original = deepcopy(snapshot)
    artifacts = SimpleNamespace(with_revisions=lambda _: SimpleNamespace(catalog=lambda: {"papers": []}))
    state = input_state(snapshot, artifacts)
    state["report"]["narrative_markdown"] = "Changed only in the candidate"
    state["revisions"]["fixture"] = {}
    state["synthesis"]["title"] = "Changed only in the candidate"
    assert snapshot == original


@pytest.mark.parametrize("spent,unknown", [(3.0, False), (0.0, True)])
def test_comparison_stops_before_transport_on_budget_or_unknown_usage(spent, unknown):
    profile, basis, _, _ = model_settings(Path(__file__).resolve().parents[1])
    model = SimpleNamespace(_get_request_payload=lambda *a, **k: {"messages": [], "tools": []})
    audit = ComparisonAudit(shared={"spent": spent, "unknown": unknown}, model=model, actor="fixture",
        profile=profile, basis=basis, public_sink=lambda _: None, private_sink=lambda _: None)
    async def forbidden(_):
        pytest.fail("A blocked budget must not invoke transport")
    with pytest.raises(ValueError, match="budget_reserve_insufficient"):
        asyncio.run(audit.awrap_model_call(SimpleNamespace(system_message=None, messages=[], tools=[]), forbidden))


def test_comparison_preserves_existing_audit_and_counts_one_response():
    profile, basis, _, _ = model_settings(Path(__file__).resolve().parents[1])
    events, private = [], []
    model = SimpleNamespace(_get_request_payload=lambda *a, **k: {"messages": [], "tools": []})
    audit = ComparisonAudit(shared={"spent": 0, "unknown": False}, model=model, actor="fixture",
        profile=profile, basis=basis, public_sink=events.append, private_sink=private.append)
    async def fixture(_):
        return SimpleNamespace(result=[AIMessage(content="Fixture only", usage_metadata={
            "input_tokens": 10, "output_tokens": 2, "total_tokens": 12,
            "input_token_details": {"cache_read": 4}}, response_metadata={"finish_reason": "stop"})])
    asyncio.run(audit.awrap_model_call(SimpleNamespace(system_message=None, messages=[], tools=[]), fixture))
    assert [e["event"] for e in events] == ["started", "outcome"]
    assert events[-1]["usage_reported"] and events[-1]["cache_hit_tokens"] == 4
    assert [e["event"] for e in private] == ["request", "response"]
