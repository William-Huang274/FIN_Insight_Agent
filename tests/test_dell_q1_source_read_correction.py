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
from sec_agent.agent_runtime.dell_specialist_agentic_graph import (
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
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentError
    from test_dell_deepseek_structured_agents import _config, _agentic_turn_request, _agentic_action
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
        with pytest.raises(DeepSeekStructuredAgentError):
            adapter.specialist_model_turn(request)
        assert len(wires) == 1 and len(private) == 1
        assert "Synthetic private" not in json.dumps(public)
        return
    adapter.specialist_model_turn(request)
    adapter.specialist_model_turn(request)
    assert len(wires) == 2
    assert all(w["tool_choice"] == "auto" for w in wires)
    assert all(len(w["tools"]) == 5 for w in wires)
    assert all(t["function"]["parameters"]["type"] == "object" for t in wires[0]["tools"])
    prior = next(m for m in wires[1]["messages"] if m["role"] == "assistant")
    assert prior["reasoning_content"] == "Synthetic private provider reasoning, not evidence."
    assert wires[1]["messages"][-1]["role"] == "tool"
    assert len(private) == 2 and "reasoning_content" in json.dumps(private)
    assert "Synthetic private" not in json.dumps(public)


@pytest.mark.local_data_integration
def test_real_mcp_source_read_finance_feedback_and_source_bound_submission():
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT, _RealMCPFakeModel, _assert_assets
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    _assert_assets()
    observed_requests = []

    def driver(request):
        observed_requests.append(request)
        n = len(observed_requests)
        base = {"context_digest": request["context_digest"], "reason_summary": "Offline integration, not model research."}
        items = [i for o in request["notebook"]["observations"] for i in o["content"]]
        if n == 1:
            return {**base, "action": "request_source", "selection": {"operation": "search", "query": "Dell AI server orders backlog", "limit": 12}}
        if n == 2:
            row = next(i for i in items if i.get("issuer_id") == "DELL" and i.get("document_id"))
            return {**base, "action": "request_source", "selection": {"operation": "read", "document_id": row["document_id"], "node_id": row["node_id"]}}
        if n in {3, 4}:
            return {**base, "action": "request_finance", "intent": {"ticker": "DELL",
                "metric_ids": ["cash_and_equivalents"], "granularity": "quarter_discrete" if n == 3 else "instant",
                "selection_mode": "latest_on_or_before"}}
        if n == 5:
            return _RealMCPFakeModel._evidence_action(context_digest=request["context_digest"], complete_route=True)
        passage = next(i for i in items if i.get("result_state") == "source_bound_passage")
        f2 = next(i for i in items if i.get("result_state") == "reviewed_evidence" and i.get("source_family_ref") == "F2_DELL_IR_EARNINGS")
        fact = next(i for i in items if i.get("result_state") == "numeric_fact")
        assert "available_period_roles" in json.dumps(items)
        return {**base, "action": "submit_workpaper", "terminal_state": "supported", "thesis": "Fixture only",
            "mechanism": "Separate source roles", "narrative_markdown": "Fixture only, not a real research conclusion.",
            "counterevidence": ["Source may be parsed incorrectly"], "what_would_change": ["A source correction"],
            "claims": [
                {"claim_id": "text", "kind": "reported_fact", "materiality": "high", "statement": "Source read fixture",
                 "evidence_ids": [passage["passage_id"], f2["evidence_id"]], "authority_note": "Parsed source is not S2 authority.",
                 "reasoning_summary": "Check full section and source context, not merely presence of a citation.",
                 "citation_quotes": {passage["passage_id"]: passage["passage"][:80]}},
                {"claim_id": "number", "kind": "numeric_fact", "materiality": "high", "statement": "SQL fact fixture",
                 "fact_ids": [fact["numeric_fact_id"]], "numeric_authority": "authoritative"},
            ]}

    with open_dell_specialist_scripted_qualification_composition(run_id="test:3plus1", run_invocation_id="test:3plus1:1",
        branch_id="Q1_ISSUER_TRUTH", environment=RUNTIME_ENVIRONMENT, scripted_model_turn=driver,
        source_read_enabled=True) as composition:
        result = composition.graph.invoke(composition.graph_input.model_dump(mode="json"), config={"recursion_limit": 40})
    assert result["phase"] == "specialist_submission_accepted"
    assert len(observed_requests) == 6
    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    bad = dict(result["final_submission"])
    bad["claims"][0]["citation_quotes"] = {bad["claims"][0]["evidence_ids"][0]: "THIS WAS NEVER IN THE SOURCE"}
    assert any("source_quote_not_in_observed" in e for e in _submission_errors(SubmitWorkpaperAction.model_validate_json(json.dumps(bad)), notebook))


@pytest.mark.local_data_integration
def test_original_r3_queries_now_recall_existing_guidance():
    from pathlib import Path
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    path = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-specialist-paid-shadow-r3/specialist-final-state.private.json")
    if not path.exists():
        pytest.skip("immutable R3 audit artifact unavailable")
    old = json.loads(path.read_text(encoding="utf-8"))
    old_notebook = old["values"]["notebook"]
    # Old evidence remains readable under the additive profile.
    SpecialistNotebook.model_validate_json(json.dumps(old_notebook))
    actions = [r["action"] for r in old_notebook["model_turn_records"] if r["action"]["action"] == "request_evidence"]
    position = 0
    def driver(request):
        nonlocal position
        if position < len(actions):
            action = {**actions[position], "context_digest": request["context_digest"]}
            position += 1
            return action
        return {"action": "request_human_review", "context_digest": request["context_digest"],
                "reason_summary": "Offline replay ends here; no model evaluation claimed.", "blocker_code": "offline_replay_complete"}
    with open_dell_specialist_scripted_qualification_composition(run_id="test:r3-query-replay", run_invocation_id="test:r3-query-replay:1",
        branch_id="Q1_ISSUER_TRUTH", environment=RUNTIME_ENVIRONMENT, scripted_model_turn=driver,
        source_read_enabled=True) as composition:
        result = composition.graph.invoke(composition.graph_input.model_dump(mode="json"), config={"recursion_limit": 40})
    targets = {str(i.get("target_id", "")) for o in result["notebook"]["observations"] for i in o["content"]}
    assert any("GUIDANCE" in t.upper() for t in targets), targets
