"""Surface lifecycle tests; synthetic summaries do not validate research quality."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda
from pydantic import SecretStr

from sec_agent.agent_runtime.continuous_context_surface import expand_provenance
from sec_agent.agent_runtime.model_context import project_tool_history, RequestSummaryMiddleware
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
from sec_agent.agent_runtime.source_result_view import source_message_views


def fixture():
    rows = [HumanMessage(id="task", content="Compare the original periods and preserve unresolved issues.")]
    provenance = {"snapshot": "original-v1", "conditions": "restriction and source URL " * 90}
    for n in range(5):
        navigation = n in (0, 4)
        body = {"operation": "search" if navigation else "read", "read_only": True,
                "source_snapshot_sha256": "sha", "items": [{
                    "candidate_id": f"CAND::{n}", "title": f"Exact original {n}",
                    "result_state": "retrieval_candidate" if navigation else "source_bound_passage",
                    "organization_source": provenance,
                    **({"preview": "candidate " * 200} if navigation else {
                        "passage_id": f"PASSAGE::{n}", "passage": f"FY{2020+n} USD original qualifiers " * 250,
                        "period": f"FY{2020+n}", "unit": "USD", "content_sha256": f"{n}"})}]}
        rows += [AIMessage(id=f"a{n}", content="", additional_kwargs={"reasoning_content": f"opaque-{n}"},
                           tool_calls=[{"id": f"c{n}", "name": "read_source_document", "args": {"query": str(n)}, "type": "tool_call"}]),
                 ToolMessage(id=f"t{n}", tool_call_id=f"c{n}", name="read_source_document", content=json.dumps(body))]
    return rows


def surface(rows, threshold=1, reader=True):
    return project_tool_history(rows, policy="continuous_surface", trigger_tokens=threshold, saved_result_reader=reader)


def test_pressure_retires_consumed_navigation_not_source_text_or_first_delivery():
    rows = fixture(); original = deepcopy(rows)
    view = surface(rows); expanded = expand_provenance(view)
    expected = source_message_views(rows)
    assert json.loads(view[2].content)["context_surface"]["kind"] == "consumed_navigation_index"
    assert json.loads(view[2].content)["items"][0]["original_json_pointer"] == "/items/0"
    for i in (4, 6, 8, 10):
        assert json.loads(expanded[i].content) == json.loads(expected[i].content)
    assert rows == original
    assert view == surface(view) == surface(deepcopy(rows))
    assert all(view[i] == rows[i] for i in (0, 1, 3, 5, 7, 9))


def test_no_reader_or_pressure_does_not_archive_and_metadata_refs_roundtrip():
    rows = fixture()
    for view in (surface(rows, reader=False), surface(rows, threshold=10**9)):
        expanded = expand_provenance(view)
        expected = source_message_views(rows)
        for actual, before in zip(expanded, expected):
            if actual.type == "tool":
                assert json.loads(actual.content) == json.loads(before.content)
        assert "consumed_navigation_index" not in str(view)
        assert len(str(view)) < len(str(rows))


def test_errors_unknown_results_calculation_and_changed_versions_survive():
    rows = fixture()
    for n, (status, body) in enumerate([
        ("error", {"error": "original unresolved"}),
        ("success", {"unknown_contract": "preserve original body " * 200}),
        ("success", {"calculation_id": "CALC::1", "operands": {"a": {"source_id": "PASSAGE::1", "value": "42", "unit": "USD"}}, "value_decimal": "42"}),
    ]):
        rows += [AIMessage(id=f"extra-a{n}", content="", tool_calls=[{"id": f"extra-{n}", "name": "calculate_research_metric", "args": {}, "type": "tool_call"}]),
                 ToolMessage(id=f"extra-t{n}", tool_call_id=f"extra-{n}", name="calculate_research_metric", status=status, content=json.dumps(body))]
    view = surface(rows)
    assert view[-6:] == rows[-6:]
    changed = deepcopy(rows)
    body = json.loads(changed[6].content); body["items"][0]["organization_source"]["snapshot"] = "v2"
    changed[6].content = json.dumps(body)
    expanded = expand_provenance(surface(changed))
    assert json.loads(expanded[6].content)["items"][0]["organization_source"]["snapshot"] == "v2"
    assert json.loads(expanded[4].content)["items"][0]["organization_source"]["snapshot"] == "original-v1"


def test_sdk_preserves_reasoning_pairs_and_policy_never_enters_provider_payload():
    rows = fixture()
    model = ReasoningPreservingChatDeepSeek(model="deepseek-flash", api_key=SecretStr("offline"),
        tool_context_policy="continuous_surface", tool_context_trigger_tokens=1, max_retries=0)
    payload = model._get_request_payload(rows, tools=[{"type": "function", "function": {
        "name": "read_saved_result", "parameters": {"type": "object"}}}])
    assert "tool_context_policy" not in payload
    for n in range(5):
        assert payload["messages"][1+n*2]["reasoning_content"] == f"opaque-{n}"
        assert payload["messages"][2+n*2]["tool_call_id"] == f"c{n}"


def summary_policy(calls, response="Offline lifecycle fixture; not a financial conclusion."):
    def summarize(value):
        calls.append(value)
        return AIMessage(content=response)
    return RequestSummaryMiddleware(model=FakeListChatModel(responses=["unused"]),
        audited_model=RunnableLambda(summarize), trigger_tokens=2500, keep_tokens=500,
        max_summaries=2, per_user_turn=False, context_policy="continuous_surface", navigation_trigger_tokens=1000)


def test_repeated_pressure_same_user_pair_safe_restart_and_edited_prefix_detection():
    async def run():
        calls=[]; middleware=summary_policy(calls); rows=fixture()
        original=deepcopy(rows); state={"messages": rows}
        state.update(await middleware.abefore_model(state,None))
        assert state["request_summary"]["count"] == 1
        assert state["messages"] == original
        assert "PASSAGE::1" in state["request_summary"]["message"]["content"]
        view=middleware.projected_messages(state)
        assert view[0] == rows[0] and view[-2:] == rows[-2:]
        restored=deepcopy(state)
        assert middleware.projected_messages(restored) == view
        serialized=json.loads(json.dumps({"messages":[m.model_dump(mode="json") for m in state["messages"]],
                                          "request_summary":state["request_summary"]}))
        kinds={"human":HumanMessage,"ai":AIMessage,"tool":ToolMessage}
        serialized["messages"]=[kinds[m["type"]].model_validate(m) for m in serialized["messages"]]
        assert middleware.projected_messages(serialized)==view
        assert await middleware.abefore_model(restored,None) is None
        # Same user, new research: recompact under pressure, not once per user.
        for n in range(3):
            state["messages"] += [AIMessage(id=f"new-a{n}",content="", tool_calls=[{"id": f"new-{n}", "name": "read_source_document", "args": {}, "type": "tool_call"}]),
                ToolMessage(id=f"new-t{n}",tool_call_id=f"new-{n}",name="read_source_document",content="New exact evidence with qualifiers " * 300)]
        state.update(await middleware.abefore_model(state,None))
        assert state["request_summary"]["count"] == 2 and len(calls)==2
        assert middleware.projected_messages(state)[-2:] == state["messages"][-2:]
        # Same boundary IDs, altered interior: stale summary must fail.
        state["messages"][2] = state["messages"][2].model_copy(update={"content":"edited interior"})
        with pytest.raises(ValueError, match="history_changed"):
            middleware.projected_messages(state)
    asyncio.run(run())


def test_selected_profile_uses_existing_factory_and_preserves_research_limits(monkeypatch):
    from pathlib import Path
    from sec_agent.agent_runtime.conversation_summary import summary_middleware
    from sec_agent.agent_runtime.case_review_agent import case_chat_model
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
    from types import SimpleNamespace
    root=Path(__file__).resolve().parents[1]
    original=json.loads((root/'configs/research/runtime/conversation.json').read_text(encoding='utf-8'))
    baseline=json.loads((root/'configs/research/runtime/continuous_context_baseline.json').read_text(encoding='utf-8'))
    assert baseline['summary']['profile']['reasoning_effort'] == 'high'
    assert baseline['summary']['budget']['max_output_tokens'] == 12000
    assert baseline['summary']['budget']['max_transport_attempts'] == 1
    spec={**original,**baseline}
    assert spec['limits']==original['limits'] and spec['budget']==original['budget'] and spec['profile']==original['profile']
    monkeypatch.setenv('DEEPSEEK_API_KEY','offline-fixture')
    middleware=summary_middleware(spec,public=lambda _:None,private=lambda _:None,access_check=None,budget_scope=None)
    assert middleware.context_policy=='continuous_surface' and not middleware.per_user_turn
    assert middleware.native.keep==('tokens',12000) and middleware.trigger_tokens==32000
    model=case_chat_model(DeepSeekModelProfile.model_validate(spec['profile']),TokenBudgetBasis.model_validate_json(json.dumps(spec['budget'])),
        SimpleNamespace(base_url='https://api.deepseek.com'),SecretStr('offline-fixture'),context_editing=spec['context_editing'])
    assert model.tool_context_policy=='continuous_surface'
    with pytest.raises(ValueError, match='pressure_based'):
        RequestSummaryMiddleware(model=FakeListChatModel(responses=['unused']),audited_model=RunnableLambda(lambda _:None),
            trigger_tokens=32000,keep_tokens=12000,per_user_turn=True,context_policy='continuous_surface')


def test_larger_summary_not_promoted_or_automatically_retried():
    async def run():
        calls=[]; middleware=summary_policy(calls, "oversized fixture " * 12000)
        state={"messages":fixture()}; original=deepcopy(state)
        state.update(await middleware.abefore_model(state,None))
        assert state["request_summary_failure"]["reason"] == "summary_did_not_reduce_context"
        assert state["messages"] == original["messages"] and "request_summary" not in state
        assert await middleware.abefore_model(state,None) is None and len(calls)==1
    asyncio.run(run())

def test_continuous_summary_receives_task_and_correction_without_changing_cutoff():
    async def run():
        calls=[]
        middleware=summary_policy(calls, 'Fixture working memory.')
        rows=fixture()
        rows[0].content='Original task with literal {messages} and {"period": "FY2026"}.'
        rows.insert(1,HumanMessage(id='correction',content='Compare cash flow; do not produce a report yet.'))
        original=deepcopy(rows)
        native_prompt=middleware.native.summary_prompt
        update=await middleware.abefore_model({'messages':rows},None)
        assert update and 'request_summary' in update
        prompt=calls[0]
        assert prompt[0] == rows[0]
        assert rows[1].content in prompt[-1].content
        assert '## SESSION INTENT' not in str(prompt)
        assert 'Create a concise continuation checkpoint' in prompt[-1].content
        assert any(isinstance(m, ToolMessage) for m in prompt)
        assert 'opaque-' not in str(prompt)
        assert middleware.native.summary_prompt==native_prompt
        assert rows==original
        view=middleware.projected_messages({'messages':rows,**update})
        assert view[0]==rows[0] and rows[1] in view and view[-2:]==rows[-2:]
        # A different request using the same middleware must not inherit task data.
        other=fixture();other[0].content='Independent second task'
        await middleware.abefore_model({'messages':other},None)
        assert 'Independent second task' in str(calls[1]) and 'Original task with literal' not in str(calls[1])
    asyncio.run(run())
