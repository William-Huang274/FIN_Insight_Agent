from __future__ import annotations

from hashlib import sha256
import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from sec_agent.research_foundation.source_document_navigation import (
    SourceDocumentRequest, navigate_source_nodes,
)
from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek,
)
from sec_agent.agent_runtime.specialist_graph import (
    SpecialistNotebook, SubmitWorkpaperAction, _submission_errors,
)


def _node(kind="section", content="Revenue table: USD millions. FY2027 Q1: 123. Note: unaudited."):
    return dict(node_id="SECTION::1", parent_document_id="DOC::1", parent_section_id="SECTION::1",
                node_kind=kind, stable_url="https://www.sec.gov/example", content=content,
                content_sha256=sha256(content.encode()).hexdigest(), document_kind="html",
                section_path=["Results"], publication_date="2026-06-01", issuer_id="DELL")


def test_source_read_preserves_full_table_and_separates_authority():
    row = _node()
    result = navigate_source_nodes([row], SourceDocumentRequest(operation="read", document_id="DOC::1"), snapshot="a" * 64)
    item = result.items[0]
    assert item["passage"] == row["content"]
    assert item["writer_citable"] is True
    assert item["numeric_fact_authority"] is False
    assert item["truncated"] is False
    assert item["source_locator"]["node_id"] == row["node_id"]


def test_catalog_company_filter_applies_before_pagination_and_empty_is_not_full_menu():
    rows = [{**_node(), 'company': 'Example Devices', 'ticker': 'DEV', 'title': 'Quarter results'},
        {**_node(), 'node_id': 'SECTION::2', 'parent_document_id': 'DOC::2',
         'company': 'Other Company', 'ticker': 'OTH', 'title': 'Annual report'}]
    def catalog(query, offset=0):
        return navigate_source_nodes(rows, SourceDocumentRequest(operation='catalog', query=query,
            offset=offset, limit=1), snapshot='fixture')
    assert catalog('dev').items[0]['document_id'] == 'DOC::1'
    assert catalog('other').items[0]['document_id'] == 'DOC::2'
    assert catalog('missing company').total_matches == 0
    assert catalog('dev', 1).items == ()
    assert catalog('*').total_matches == catalog('').total_matches == 2
    assert catalog('dev').items[0]['writer_citable'] is False


@pytest.mark.parametrize("selection,code", [
    ({"operation": "read", "document_id": "DOC::foreign"}, "not_in_approved"),
    ({"operation": "read", "document_id": "DOC::1", "node_id": "SECTION::foreign"}, "not_in_selected"),
    ({"operation": "read", "document_id": "DOC::1", "page_start": 2}, "html_has_no"),
])
def test_source_outside_scope_rejected(selection, code):
    with pytest.raises(ValueError, match=code):
        navigate_source_nodes([_node()], SourceDocumentRequest(**selection), snapshot="a" * 64)


@pytest.mark.parametrize("bad", ["D:/secrets/.env", "../../secrets", "https://localhost/admin", "file:///etc/passwd"])
def test_raw_paths_and_urls_are_not_resource_ids(bad):
    with pytest.raises(ValidationError):
        SourceDocumentRequest(operation="read", document_id=bad)


def test_no_silent_truncation_and_search_is_not_citable():
    row = _node(content="source text " * 500)
    result = navigate_source_nodes([row], SourceDocumentRequest(operation="read", document_id="DOC::1", max_characters=2000), snapshot="a" * 64)
    assert result.items == () and result.next_offset == 0
    assert "without truncating" in result.notice
    child = {**row, "node_kind": "chunk"}
    result = navigate_source_nodes([child], SourceDocumentRequest(operation="search", query="source"), snapshot="a" * 64)
    assert result.items[0]["writer_citable"] is False


@pytest.mark.parametrize("tool_case", ["valid", "wrong_action_tag"])
def test_provider_tool_history_retains_reasoning_on_actual_sdk_wire(tool_case):
    from test_deepseek_structured_agents import _config, _agentic_turn_request, _agentic_action
    wires, private, public = [], [], []
    request = _agentic_turn_request()

    def respond(req):
        wire = json.loads(req.content)
        wires.append(wire)
        action = _agentic_action(context_digest=request["context_digest"])
        if tool_case == "wrong_action_tag":
            action["action"] = "request_finance"
        calls = [{"id": f"action-{len(wires)}", "type": "function", "function": {
            "name": "UnregisteredTool" if tool_case == "wrong_name" else "RequestHumanReviewAction",
            "arguments": json.dumps(action),
        }}]
        if tool_case == "multiple":
            calls.append({**calls[0], "id": "unexpected-second-call"})
        return httpx.Response(200, json={
            "id": f"mock-{len(wires)}", "object": "chat.completion", "created": 1, "model": "deepseek-v4-pro",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": "", "reasoning_content": "Synthetic private provider reasoning, not evidence.",
                "tool_calls": calls,
            }}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

    model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("mock-no-network"),
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        max_retries=0, extra_body={"thinking": {"type": "enabled"}}, use_responses_api=False)
    config = _config().model_copy(update={"thinking": "enabled", "agentic_message_history": True})
    adapter = DeepSeekStructuredAgentAdapter(config=config,
        chat_models={r: model for r in ("planner", "specialist", "counter", "lead")},
        private_audit_sink=private.append, audit_sink=public.append)
    if tool_case != "valid":
        result = adapter.specialist_model_turn(request)
        assert result["action"]["action"] == "native_tool_batch"
        assert result["action"]["tool_calls"][0]["args"]["action"] == "request_finance"
        assert len(wires) == 1 and len(private) == 2
        assert private[0]["event"] == "request"
        assert private[0]["call_id"] == private[1]["call_id"]
        assert "Synthetic private" not in json.dumps(public)
        return
    adapter.specialist_model_turn(request)
    adapter.specialist_model_turn(request)
    assert len(wires) == 2
    assert all(w["tool_choice"] == "auto" for w in wires)
    expected_tools = {
        "RequestEvidenceAction", "RequestFinanceAction",
        "SubmitWorkpaperAction", "RequestHumanReviewAction",
    }
    assert all({t["function"]["name"] for t in w["tools"]} == expected_tools for w in wires)
    assert all(t["function"]["parameters"]["type"] == "object" for t in wires[0]["tools"])
    prior = next(m for m in wires[1]["messages"] if m["role"] == "assistant")
    assert prior["reasoning_content"] == "Synthetic private provider reasoning, not evidence."
    assert wires[1]["messages"][-1]["role"] == "tool"
    assert len(private) == 4 and "reasoning_content" in json.dumps(private)
    assert sum(row.get("event") == "request" for row in private) == 2
    assert "Synthetic private" not in json.dumps(public)
