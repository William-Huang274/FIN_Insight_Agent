"""Native loop / MCP / citation qualification, not a semantic gold evaluation."""
import asyncio
import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from mcp import Client
import pytest

from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
from sec_agent.agent_runtime.dell_case_review_agent import (
    CaseReview, build_case_reviewer, build_case_review_graph, case_mcp_tools, validate_case_review,
)
from test_dell_research_mcp import _build_server


@pytest.fixture(scope="module")
def artifacts():
    from scripts.qualification.dell_q1_specialist_paid_shadow.collect_research_bundle import SOURCES, collect
    if not all(p.is_file() for p, _ in SOURCES):
        pytest.skip("local immutable research artifacts unavailable")
    return DellCaseArtifacts(collect()["papers"])


def review_fixture(artifacts):
    return {"summary": "Synthetic native-loop qualification only; not a real financial review or product PASS.",
        "assessments": [{"paper_id": p["paper_id"], "assessment": "Fixture checked tool access only, no semantic verdict."}
                        for p in artifacts.catalog()["papers"]], "findings": [], "unresolved_data_requests": []}


class ScriptedNativeChat(BaseChatModel):
    replies: list
    marker: str

    @property
    def _llm_type(self):
        return "zero-provider-native-loop-fixture"

    def bind_tools(self, tools, **kwargs):
        names = {t.name for t in tools}
        assert {"read_research_artifact", "calculate_research_metric", "submit_case_review"}.issubset(names)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        for message in messages:
            if isinstance(message, AIMessage):
                assert message.additional_kwargs["reasoning_content"] == self.marker
        index = sum(isinstance(m, AIMessage) for m in messages)
        reply = self.replies[index]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=reply,
            additional_kwargs={"reasoning_content": self.marker}))])


def call(name, args, identity):
    return {"name": name, "args": args, "id": identity, "type": "tool_call"}


def test_native_parallel_agents_errors_and_checkpointed_private_messages(artifacts):
    async def exercise():
        server = _build_server(case_artifacts=artifacts)
        async with Client(server, raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            source_id = next(s for s, item in artifacts.read_paper("P01", "sources").items() if item["result_state"] == "numeric_fact")
            read_calls = [call("read_research_artifact", {"paper_id": p["paper_id"]}, f"read{i}")
                          for i, p in enumerate(artifacts.catalog()["papers"])]
            good = review_fixture(artifacts)
            bad = {**good, "findings": [{"finding_id": "F1", "paper_id": "P01", "severity": "material",
                "problematic_quote": "THIS IS NOT IN THE ACTUAL PAPER", "diagnosis": "Synthetic exact quote negative.",
                "requested_change": "Correct the synthetic quote only."}]}
            replies = [read_calls, [call("read_research_source", {"source_id": "unknown"}, "badsource")],
                [call("calculate_research_metric", {"request": {"expression": "a / 2", "operands": {"a": {"source_id": source_id}},
                    "result_unit": "fixture", "rationale": "Test arithmetic only, not economic interpretation."}}, "calc")],
                [call("submit_case_review", {"review": bad}, "badreview")],
                [call("submit_case_review", {"review": good}, "goodreview")]]
            reviewers = {r: build_case_reviewer(role=r, model=ScriptedNativeChat(replies=replies, marker=r),
                tools=tools, artifacts=artifacts) for r in ("counter", "verifier")}
            saver = InMemorySaver()
            graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question="Synthetic native qualification",
                run_id="run-test", run_invocation_id="invoke-test").compile(checkpointer=saver)
            assert {name for name, _ in graph.get_subgraphs()} == {"counter", "verifier"}
            result = await graph.ainvoke({"run_id": "run-test", "run_invocation_id": "invoke-test"},
                {"configurable": {"thread_id": "fixture-thread"}, "recursion_limit": 150})
            assert result["phase"] == "case_review_ready_for_convergence"
            assert result["counter"]["model_calls"] == result["verifier"]["model_calls"] == 5
            assert "messages" not in result and "reasoning_content" not in json.dumps(result)
            checkpoints = list(saver.list(None))
            for role in ("counter", "verifier"):
                own = [c for c in checkpoints if c.config["configurable"].get("checkpoint_ns", "").startswith(role + ":")]
                assert own
                messages = max(own, key=lambda c: len(c.checkpoint["channel_values"].get("messages", []))).checkpoint["channel_values"]["messages"]
                ai = [m for m in messages if isinstance(m, AIMessage)]
                assert len(ai) == 5 and all(m.additional_kwargs["reasoning_content"] == role for m in ai)
                rejected = [m for m in messages if isinstance(m, ToolMessage) and m.status == "error"]
                assert len(rejected) == 2
                assert any("problematic_quote_not_exact" in m.content for m in rejected)
                assert all(isinstance(m.artifact, dict) for m in messages if isinstance(m, ToolMessage) and m.name == "read_research_artifact")
    asyncio.run(exercise())


def test_cannot_claim_all_papers_read_without_observation(artifacts):
    with pytest.raises(ValueError, match="read_missing_papers"):
        validate_case_review(CaseReview.model_validate(review_fixture(artifacts)), artifacts, [])


def test_review_returns_all_independent_quote_errors_at_once(artifacts):
    data = review_fixture(artifacts)
    data["findings"] = [{"finding_id": fid, "paper_id": "P01", "severity": "material",
        "problematic_quote": "SYNTHETIC MISSING QUOTE", "claim_ids": ["nonexistent"],
        "diagnosis": "Synthetic quote regression, not a financial finding.",
        "requested_change": "Correct all independent errors together.",
        "source_checks": [{"source_id": "P01:S001", "quote": "SYNTHETIC WRONG SOURCE QUOTE"},
                          {"source_id": "P99:S001", "quote": "missing source"}]}
        for fid in ("F1", "F2")]
    with pytest.raises(ValueError) as caught:
        validate_case_review(CaseReview.model_validate(data), artifacts, [])
    errors = json.loads(str(caught.value))["errors"]
    assert len(errors) == 9  # read coverage plus four independent errors per finding
    for fid in ("F1", "F2"):
        assert f"problematic_quote_not_exact:{fid}" in errors
        assert f"source_quote_not_exact:{fid}:P01:S001" in errors
        assert f"unknown_source_id:{fid}:P99:S001" in errors


def test_case_schema_factory_is_read_only_and_discovers_both_subgraphs(monkeypatch):
    from types import SimpleNamespace
    import sec_agent.agent_runtime.dell_agent_server_entry as entry
    monkeypatch.setenv("FINSIGHT_DELL_SERVING_MODE", "case_workpaper_review_v1")
    monkeypatch.setattr(entry, "open_case_review_composition", lambda **kwargs: pytest.fail("schema read opened case/model/data"))

    async def exercise():
        async with entry.dell_reference_vertical_graph({}, SimpleNamespace(execution_runtime=None)) as graph:
            assert {name for name, _ in graph.get_subgraphs()} == {"counter", "verifier"}
            assert "counter" in graph.get_output_jsonschema()["properties"]
    asyncio.run(exercise())


def test_source_tool_scopes_hidden_and_injected(artifacts):
    async def exercise():
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            binding = await client.call_tool("get_dell_research_method", {"branch_ids": ["Q1_ISSUER_TRUTH"],
                "research_as_of": "2026-09-02T00:00:00Z", "data_snapshot_id": "fixture", "execution_attempt_id": "fixture"})
            assert not binding.is_error
            tools = await case_mcp_tools(client, run_scope=binding.structured_content["run_scope"])
            finance = next(t for t in tools if t.name == "query_company_financial_facts")
            assert "run_scope" not in finance.args
            assert finance.args["branch_id"]["enum"] == ["Q1_ISSUER_TRUTH"]
            assert "fiscal_year" in finance.args["granularity"]["enum"]
            assert "annual" not in finance.args["granularity"]["enum"]
            response = await finance.ainvoke(call("query_company_financial_facts", {
                "branch_id": "NOT_ALLOWED", "ticker": "DELL", "metric_ids": ["revenue"],
                "research_as_of": "2026-09-02", "granularity": "quarter_discrete", "selection_mode": "latest_on_or_before"}, "badbranch"))
            assert response.status == "error" and "branch_outside_case_scope" in response.content
    asyncio.run(exercise())


def test_actual_case_data_plane_with_native_MCP_tool_projection(artifacts):
    from sec_agent.agent_runtime.dell_agent_server_data_composition import open_dell_approved_data_composition
    from test_dell_agent_server_data_composition import DEFAULT_ARTIFACT_ENV
    with open_dell_approved_data_composition(run_invocation_id="case-native-zero-model-host",
            environment=DEFAULT_ARTIFACT_ENV, source_read_enabled=True, case_artifacts=artifacts) as data:
        assert artifacts.case_id == data.foundation_binding.case_id
        assert artifacts.foundation_digest == data.foundation_binding.foundation_digest
        assert artifacts.snapshot_id == data.foundation_binding.snapshot_id
        assert artifacts.owner_data_gate_decision_digest == data.decision_digest
        assert artifacts.inventory_snapshot_digest == data.inventory_snapshot_digest
        assert artifacts.source_route_catalog_digest == data.source_route_catalog_digest
        async def exercise():
            async with Client(data.mcp_server, raise_exceptions=False) as client:
                args = {"research_as_of": artifacts.research_as_of, "data_snapshot_id": artifacts.snapshot_id,
                    "execution_attempt_id": "case-native-zero-model-host"}
                branches = sorted({p["branch_id"] for p in artifacts.catalog()["papers"]})
                binding = await client.call_tool("get_dell_research_method", {"branch_ids": branches, **args})
                assert not binding.is_error
                tools = {t.name: t for t in await case_mcp_tools(client, run_scope=binding.structured_content["run_scope"], method_arguments=args)}
                assert len(tools) == 8
                method = await tools["get_dell_research_method"].ainvoke(call("get_dell_research_method", {"branch_ids": branches}, "method"))
                assert "scope_ceiling" not in method.artifact and "execution_budget_notice" in method.artifact
                catalog = await tools["read_source_document"].ainvoke(call("read_source_document", {
                    "request": {"operation": "catalog"}, "branch_id": "Q1_ISSUER_TRUTH"}, "catalog"))
                assert catalog.status == "success" and catalog.artifact["items"]
                facts = await tools["query_company_financial_facts"].ainvoke(call("query_company_financial_facts", {
                    "branch_id": next(b for b in branches if b.startswith("Q8_")), "ticker": "DELL", "metric_ids": ["revenue"],
                    "research_as_of": "2026-09-02", "granularity": "fiscal_year", "fiscal_years": [2026],
                    "selection_mode": "latest_on_or_before"}, "facts"))
                assert facts.status == "success", facts.content
                assert "numeric_fact" in facts.content
        asyncio.run(exercise())


def test_real_DeepSeek_SDK_native_requests_usage_and_reasoning_preservation(artifacts):
    import httpx
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import (
        ReasoningPreservingChatDeepSeek, load_deepseek_structured_agent_config,
    )
    from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit
    request_rows, public, private = [], [], []
    config = load_deepseek_structured_agent_config("configs/research/fin_ia_0_1_3_dell_q8_targeted_completion_v1_0.json")
    replies = [[call("read_research_artifact", {"paper_id": p["paper_id"]}, f"read{i}")
               for i, p in enumerate(artifacts.catalog()["papers"])],
               [call("submit_case_review", {"review": review_fixture(artifacts)}, "submit")]]

    def serve(request):
        body = json.loads(request.content)
        index = len(request_rows)
        request_rows.append(body)
        assert all(t["function"]["parameters"]["type"] == "object" for t in body["tools"])
        if index == 1:
            prior = next(m for m in body["messages"] if m["role"] == "assistant")
            assert prior["reasoning_content"] == "private fixture reasoning preserved verbatim"
            assert len([m for m in body["messages"] if m["role"] == "tool"]) == 10
        return httpx.Response(200, json={"id": f"fixture{index}", "object": "chat.completion", "created": 1,
            "model": "deepseek-v4-pro", "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": "", "reasoning_content": "private fixture reasoning preserved verbatim",
                "tool_calls": [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["args"])}} for c in replies[index]]}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "prompt_cache_hit_tokens": 40,
                "prompt_cache_miss_tokens": 60, "completion_tokens_details": {"reasoning_tokens": 30}}})

    async def exercise():
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client, httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http_client:
            model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("fixture-not-a-secret"),
                http_async_client=http_client, max_retries=0, streaming=False, use_responses_api=False,
                extra_body={"thinking": {"type": "enabled"}})
            agent = build_case_reviewer(role="verifier", model=model, tools=await case_mcp_tools(client), artifacts=artifacts,
                audit=CaseModelAudit(actor="case_verifier", profile=config.profile_for("verifier"), basis=config.token_budget_basis["specialist"],
                    public_sink=public.append, private_sink=private.append))
            result = await agent.ainvoke({"messages": [{"role": "user", "content": "Fixture native loop qualification, not real research."}]})
            assert result["review"] == review_fixture(artifacts)
    asyncio.run(exercise())
    assert len(request_rows) == 2 and len(public) == 4 and len(private) == 4
    assert sum(r.get("total_tokens", 0) for r in public) == 300
    assert [r["cache_hit_tokens"] for r in public if r["event"] == "outcome"] == [40, 40]
    assert "private fixture" not in json.dumps(public) and "private fixture" in json.dumps(private)
