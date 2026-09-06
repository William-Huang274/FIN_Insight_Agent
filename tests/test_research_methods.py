import asyncio

import pytest
from mcp import Client

from sec_agent.research_foundation.research_methods import METHODS, get_research_method
from test_dell_research_mcp import _build_server


def test_method_catalog_is_compact_answer_free_and_content_is_packaged():
    catalog = get_research_method()
    assert {row["method_id"] for row in catalog["methods"]} == set(METHODS)
    assert all("content" not in row for row in catalog["methods"])
    for method_id in METHODS:
        method = get_research_method(method_id)
        assert method["content"] and method["answer_free"] and not method["grants_authority"]
        assert "Dell" not in method["content"] and "DELL" not in method["content"]


@pytest.mark.parametrize("method_id", ["../../.env", "D:/private.txt", "unknown", "finance.md"])
def test_method_reader_does_not_accept_paths_or_unknown_resources(method_id):
    with pytest.raises(ValueError, match="unknown_research_method"):
        get_research_method(method_id)


def test_actual_mcp_progressive_method_read_and_rejection():
    async def exercise():
        async with Client(_build_server(), raise_exceptions=False) as client:
            catalog = await client.call_tool("get_research_method", {})
            assert not catalog.is_error and len(catalog.structured_content["methods"]) == 6
            method = await client.call_tool("get_research_method", {"method_id": "finance"})
            assert not method.is_error
            assert "利润率变化用百分点" in method.structured_content["content"]
            assert "不是预测" in method.structured_content["content"]
            rejected = await client.call_tool("get_research_method", {"method_id": "../../.env"})
            assert rejected.is_error
    asyncio.run(exercise())


def test_specialist_method_action_consumes_actual_mcp_without_general_disclosure_or_source_authority():
    import json
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    from test_dell_agent_server_data_composition import DEFAULT_ARTIFACT_ENV
    requests = []

    def model(request):
        requests.append(request)
        if len(requests) == 1:
            assert "request_method" in request["allowed_actions"]
            assert "request_disclosure" not in request["allowed_actions"]
            return {"action": "native_tool_batch", "context_digest": request["context_digest"], "tool_calls": [{
                "id": "method-read", "name": "RequestResearchMethodAction", "type": "tool_call",
                "args": {"action": "request_method", "context_digest": request["context_digest"],
                         "reason_summary": "Read the financial research method.", "method_id": "finance"}}]}
        assert "利润率变化用百分点" in request["tool_results"][0]["content"]
        return {"action": "request_human_review", "context_digest": request["context_digest"],
                "reason_summary": "Zero-model fixture ended; this is not research completion.", "blocker_code": "fixture_complete"}

    with open_dell_specialist_scripted_qualification_composition(
        run_id="method-host-fixture", run_invocation_id="method-mcp-fixture", branch_id="Q1_ISSUER_TRUTH",
        environment=DEFAULT_ARTIFACT_ENV, scripted_model_turn=model,
    ) as composition:
        result = composition.graph.invoke(composition.graph_input.model_dump(mode="json"))
    assert len(requests) == 2
    assert result["notebook"]["tool_action_count"] == 1
    assert not result["notebook"]["observations"]
    message = requests[1]["tool_results"][0]
    assert message["artifact"]["mcp_receipt"]["tool_name"] == "get_research_method"
    assert json.loads(message["content"])["method_id"] == "finance"
    assert result.get("final_submission") is None


def test_new_question_reaches_specialist_without_rewriting_frozen_method_or_reusing_answers():
    import json
    from pathlib import Path
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    from test_dell_agent_server_data_composition import DEFAULT_ARTIFACT_ENV

    root = Path(__file__).resolve().parents[1]
    profile = json.loads((root / "configs/research/cases/dell_growth_quality.json").read_text(encoding="utf-8"))
    frozen_path = root / "configs/research/fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
    original = frozen_path.read_bytes()
    requests = []

    def model(request):
        requests.append(request)
        return {"action": "request_human_review", "context_digest": request["context_digest"],
                "reason_summary": "Input projection fixture only, not paid research.", "blocker_code": "fixture_complete"}

    inputs = []
    for question in (None, profile["question"]):
        with open_dell_specialist_scripted_qualification_composition(
            run_id="question-fixture", run_invocation_id="question-fixture-1", branch_id="Q1_ISSUER_TRUTH",
            environment=DEFAULT_ARTIFACT_ENV, scripted_model_turn=model, research_question=question,
        ) as composition:
            inputs.append(composition.graph_input)
            composition.graph.invoke(composition.graph_input.model_dump(mode="json"))
    historical, current = inputs
    assert current.task.foundation_digest == historical.task.foundation_digest
    assert current.task.method_digest == historical.task.method_digest
    assert current.task.plan_digest != historical.task.plan_digest
    assert current.task_context["research_question"] == profile["question"]
    assert profile["question"] in requests[1]["task"]["objective"]
    view = requests[1]["l0_context"]["skill_summaries"][0]["method_context"]
    assert view["research_question"] == profile["question"]
    assert "case_identity" not in view and "acceptance_and_stop" not in view
    assert "question_branches" not in view and "scope_ceiling" not in view
    assert "source_families" in view and "formulas" in view
    assert "current_user_research_request" in json.dumps(requests[1])
    assert not current.collaboration_context
    assert frozen_path.read_bytes() == original
    assert profile["fresh_research"] and not profile["reuse_prior_workpapers"]
