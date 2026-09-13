import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from mcp import Client
import pytest

from sec_agent.agent_runtime.dell_case_convergence_agent import (
    CaseReport, PaperRevision, build_case_output_agent, build_case_convergence_graph,
    report_citations, report_model_view, validated_revision,
)
from sec_agent.agent_runtime.dell_case_review_agent import case_mcp_tools
from test_dell_case_review_agent import artifacts, call
from test_dell_research_mcp import _build_server


PAPERS = ("P01", "P04", "P05", "P06", "P07", "P08")


def revision_fixture(artifacts, pid):
    paper = artifacts.read_paper(pid)
    return {"paper_id": pid, **{k: paper[k] for k in ("thesis", "mechanism", "narrative_markdown",
        "counterevidence", "what_would_change", "open_gaps")}, "claim_updates": [], "removed_claim_ids": [],
        "finding_responses": [{"finding_id": "fixture", "disposition": "disagreed_with_sources",
            "explanation": "Synthetic fixture exercises original artifact preservation, not an actual correction."}]}


def test_revision_uses_canonical_boundary_contract_without_weakening_factual_sources(artifacts):
    request = revision_fixture(artifacts, "P01")
    request["claim_updates"] = [{"claim_id": "boundary_fixture", "kind": "boundary", "materiality": "medium",
        "statement": "Only the reviewed sources were inspected; this is not proof of universal non-disclosure.",
        "source_ids": [], "numeric_authority": "not_applicable", "authority_note": "Review coverage limitation, not an external fact."}]
    parsed = PaperRevision.model_validate(request)
    result = validated_revision(parsed, paper_id="P01", feedback=[{"finding_id": "fixture"}], artifacts=artifacts, messages=[])
    assert result["workpaper"]["claims"][-1]["source_ids"] == []
    request["claim_updates"][0]["kind"] = "reported_fact"
    with pytest.raises(ValueError, match="reported_fact_requires_evidence"):
        validated_revision(PaperRevision.model_validate(request), paper_id="P01", feedback=[{"finding_id": "fixture"}], artifacts=artifacts, messages=[])


def test_writer_can_recover_exact_quote_mismatch_by_reading_current_report(artifacts):
    async def run():
        ref = "P01:" + artifacts.read_paper("P01")["claims"][0]["claim_id"]
        prose = "Synthetic existing report. " * 12 + f"Original “quoted target” [{ref}]"
        report = {"title": "Quote recovery fixture", "narrative_markdown": prose,
            "citations": report_citations(prose, artifacts)}
        model = NativeFixtureModel(marker="quote-fixture", replies=[
            [call("submit_report_edits", {"edits": [{"old_str": 'Original "quoted target"', "new_str": "Revised source qualifier"}]}, "bad")],
            [call("read_current_report", {}, "reread")],
            [call("submit_report_edits", {"edits": [{"old_str": "Original “quoted target”", "new_str": "Revised source qualifier"}]}, "fixed")]])
        agent = build_case_output_agent(role="writer", model=model, tools=[], artifacts=artifacts,
            report_revision=True, limits={"model_calls": 3, "tool_calls": 3})
        result = await agent.ainvoke({"request_action": "revise", "report": report,
            "messages": [{"role": "user", "content": "Correct one qualifier using exact current text."}]})
        assert result["output"]["narrative_markdown"] == prose.replace("Original “quoted target”", "Revised source qualifier")
        assert report["narrative_markdown"] == prose
        failed = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.status == "error")
        assert "read_current_report" in failed.content
        reread = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "read_current_report")
        assert json.loads(reread.content)["narrative_markdown"] == prose
    asyncio.run(run())


class NativeFixtureModel(BaseChatModel):
    marker: str
    replies: list
    seen: list = []
    contexts: list = []

    @property
    def _llm_type(self):
        return "zero-provider-convergence-fixture"

    def bind_tools(self, tools, **kwargs):
        self.seen.append([t.name for t in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.contexts.append(messages)
        previous = [m for m in messages if isinstance(m, AIMessage)]
        assert all(m.additional_kwargs.get("reasoning_content") == self.marker for m in previous)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=self.replies[len(previous)],
            additional_kwargs={"reasoning_content": self.marker}))])


def saved_calculation_chart(artifacts):
    from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources
    from sec_agent.research_foundation.report_charts import ReportChart, bind_report_charts
    source_id = next(s for s, row in artifacts.read_paper("P01", "sources").items() if row["result_state"] == "numeric_fact")
    calculation = calculate_from_sources(SourceBoundCalculation(expression="v / 2", operands={"v": {"source_id": source_id}},
        result_unit="USD", rationale="Synthetic wiring calculation, not financial analysis"), artifacts.source_item)
    chart = ReportChart(title="Saved calculation fixture", unit="USD thousands", scale_divisor=1000,
        interpretation="Two labels share one source to exercise persisted arithmetic without external calls.",
        points=[{"label": label, "source": {"source_id": calculation["calculation_id"]}} for label in ("A", "B")])
    bound = bind_report_charts([chart], lambda ref: calculation)
    claim_id = artifacts.read_paper("P01")["claims"][0]["claim_id"]
    report = {"title": "Saved synthesis fixture", "narrative_markdown": "Synthetic source-bound research fixture, not a financial conclusion. " * 4 + f"[P01:{claim_id}]",
              "charts": bound, "citations": {}}
    return report, chart, calculation


def test_chart_model_projection_can_be_reused_without_value_or_scale_schema_guessing(artifacts):
    from sec_agent.research_foundation.report_charts import ReportChart
    report, chart, _ = saved_calculation_chart(artifacts)
    original = deepcopy(report)
    view = report_model_view(report)
    assert ReportChart.model_validate(view["charts"][0]) == chart
    assert view["chart_display_values"][0]["points"][0]["value"] == report["charts"][0]["points"][0]["value"]
    assert report == original and "citations" not in view


@pytest.mark.parametrize("role", ["writer", "synthesis"])
def test_native_next_role_can_reuse_server_saved_calculation_chart(artifacts, role):
    async def run():
        report, chart, _ = saved_calculation_chart(artifacts)
        original = deepcopy(report)
        submission = {"title": report["title"], "narrative_markdown": report["narrative_markdown"], "charts": [chart.model_dump(mode="json")]}
        name, arg = ("submit_case_report", "report") if role == "writer" else ("submit_research_synthesis", "synthesis")
        model = NativeFixtureModel(marker="saved-source", replies=[[call(name, {arg: submission}, "reuse")]])
        agent = build_case_output_agent(role=role, model=model, tools=[], artifacts=artifacts, limits={"model_calls": 2, "tool_calls": 3})
        result = await agent.ainvoke({"synthesis": report, "messages": [{"role": "user", "content": "Reuse the supplied chart bindings, not arbitrary model numbers."}]})
        assert result["output"]["charts"] == report["charts"] and report == original
        assert len(model.contexts) == 1
    asyncio.run(run())


@pytest.mark.parametrize("allow_edits", [False, True])
def test_revision_comparison_changes_only_edit_interface_not_revision_role(artifacts, allow_edits):
    async def run():
        report, _, _ = saved_calculation_chart(artifacts)
        submission = {k: v for k, v in report_model_view(report).items() if k != "chart_display_values"}
        model = NativeFixtureModel(marker="revision-mode", replies=[[
            call("submit_case_report", {"report": submission}, "submit")]])
        agent = build_case_output_agent(role="writer", model=model, tools=[], artifacts=artifacts,
            limits={"model_calls": 2, "tool_calls": 3}, report_revision=True, allow_report_edits=allow_edits)
        result = await agent.ainvoke({"report": report, "messages": [{"role": "user", "content": "Synthetic revision mode comparison."}]})
        prompt = model.contexts[0][0].content
        assert "Revise the supplied full Chinese report" in prompt
        assert "Not separately disclosed does not mean not achieved" in prompt
        assert "similar wording alone does not prove comparability" in prompt
        assert ("prefer submit_report_edits" in prompt) is allow_edits
        assert ("submit_report_edits" in model.seen[0]) is allow_edits
        assert "submit_case_report" in model.seen[0]
        assert result["output"]["charts"] == report["charts"]
    asyncio.run(run())


def test_unknown_source_error_identifies_exact_id_and_existing_read_tools(artifacts):
    with pytest.raises(ValueError) as caught:
        artifacts.source_item("CALC::not-observed")
    assert "CALC::not-observed" in str(caught.value)
    assert "read_current_source" in str(caught.value) and "sources" in str(caught.value)


def test_saved_chart_calculation_reuse_rejects_wrong_identity_authority_and_conflicts(artifacts):
    from sec_agent.research_foundation.report_charts import chart_calculation_sources
    report, _, calculation = saved_calculation_chart(artifacts)
    for change in ({"calculation_id": "CALC::invented"}, {"arithmetic_verified": False}, {"numeric_fact_authority": True}):
        damaged = deepcopy(report)
        damaged["charts"][0]["points"][0]["provenance"]["calculation"].update(change)
        with pytest.raises(ValueError, match="saved_chart_calculation_binding_invalid"):
            chart_calculation_sources(damaged)
    changed = deepcopy(report)
    changed["charts"][0]["points"][0]["provenance"]["calculation"]["value_decimal"] = "999999"
    with pytest.raises(ValueError, match="saved_chart_calculation_conflict"):
        chart_calculation_sources(report, changed)
    sources = chart_calculation_sources(report)
    sources[calculation["calculation_id"]]["value_decimal"] = "0"
    assert report["charts"][0]["points"][0]["provenance"]["calculation"] == calculation


def test_lead_can_submit_source_bound_charts_and_plain_prose_is_not_false_completion(artifacts):
    async def run():
        source_id = next(s for s, row in artifacts.read_paper("P01", "sources").items() if row["result_state"] == "numeric_fact")
        claim_id = artifacts.read_paper("P01")["claims"][0]["claim_id"]
        report = {"title": "Synthetic Lead chart submission", "narrative_markdown": "Native submission fixture, not a financial judgment. " * 6 + f"[P01:{claim_id}]",
            "charts": [{"title": "Same-source wiring fixture", "unit": artifacts.source_item(source_id)["unit"], "interpretation": "Both labels intentionally refer to the same source in this wiring test.",
                "points": [{"label": label, "source": {"source_id": source_id}} for label in ("A", "B")]}]}
        model = NativeFixtureModel(marker="lead-private", replies=[[], [call("submit_research_synthesis", {"synthesis": report}, "submit")]])
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            agent = build_case_output_agent(role="synthesis", model=model, tools=await case_mcp_tools(client), artifacts=artifacts,
                limits={"model_calls": 3, "tool_calls": 4})
            result = await agent.ainvoke({"messages": [{"role": "user", "content": "Submit a cited Lead judgment with useful source-bound charts."}]})
            assert len(model.contexts) == 2 and "No source-bound output was saved" in str(model.contexts[1])
            points = result["output"]["charts"][0]["points"]
            assert points[0]["source_id"] == source_id and points[0]["value"] == points[1]["value"]
            assert not result["output"]["charts"][0]["numeric_fact_authority"]
    asyncio.run(run())


def test_native_reviewer_can_read_and_quote_persisted_chart_only_source(artifacts):
    async def run():
        ref = "PASSAGE::WEB::saved-chart-window"
        report = {"title": "Synthetic chart review", "narrative_markdown": "Review the actual chart, not an invented source. " * 6,
            "charts": [{"title": "Synthetic chart title", "kind": "bar", "unit": "million", "interpretation": "Synthetic observation, not a real research finding.",
                "points": [{"source_id": ref, "label": "A", "series": "R", "value": 10,
                    "provenance": {"quote": "Revenue was 10 million", "value_decimal": "10", "source_provenance": {"source_url": "https://example.com/source", "numeric_fact_authority": False}}}]}]}
        review = {"summary": "Synthetic reviewer checks the source bound to the saved chart without repeating an external source fetch.",
            "findings": [{"finding_id": "chart", "severity": "advisory", "report_quote": f'"source_id": "{ref}"',
                "diagnosis": "The chart uses the saved quote correctly; this is a synthetic review-location qualification.",
                "requested_change": "Keep the quote and source visible when the chart point is inspected.", "responsibility": "writer", "paper_ids": []}]}
        model = NativeFixtureModel(marker="chart-review", replies=[
            [call("read_current_source", {"source_id": ref}, "read-chart")],
            [call("submit_report_review", {"review": {**review, "completion": "complete", "unresolved_data_requests": []}}, "review-chart")]])
        agent = build_case_output_agent(role="verifier", model=model, tools=[], artifacts=artifacts,
            limits={"model_calls": 3, "tool_calls": 4}, require_responsibility=True)
        result = await agent.ainvoke({"report": report, "messages": [{"role": "user", "content": "Review the chart and its source."}]})
        reads = [m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "read_current_source"]
        assert "Revenue was 10 million" in reads[0].content
        assert result["output"]["findings"][0]["finding_id"] == "chart"
    asyncio.run(run())


@pytest.mark.parametrize("material", [False, True])
@pytest.mark.parametrize("reuse", [False, True, "report"])
def test_six_responsible_authors_then_writer_verifier_native_checkpoints(artifacts, material, reuse):
    async def run():
        original = artifacts.read_paper("P01")
        feedback = {p: [{"finding_id": "fixture"}] for p in PAPERS}
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            limits = {"model_calls": 12, "tool_calls": 32}
            agents = {}
            reused = {}
            for pid in PAPERS:
                revision = revision_fixture(artifacts, pid)
                revision["thesis"] = "Synthetic corrected current thesis for fixture paper " + pid
                model = NativeFixtureModel(marker=pid, replies=[
                    [call("read_research_artifact", {"paper_id": pid}, "read")],
                    [call("submit_paper_revision", {"revision": revision}, "submit")]])
                agents["author_"+pid] = build_case_output_agent(role="repair", model=model, tools=tools,
                    artifacts=artifacts, feedback=feedback[pid], paper_id=pid, limits=limits)
                if reuse and (pid != "P07" or reuse == "report"):
                    reused[pid] = {"output": validated_revision(PaperRevision.model_validate(revision), paper_id=pid,
                        feedback=feedback[pid], artifacts=artifacts, messages=[]), "origin": {
                        "execution_id": "prior-fixture", "server_thread_id": "old-thread", "checkpoint_ns": "author_"+pid,
                        "checkpoint_id": "old-checkpoint", "server_run_id": "old-run", "native_submission_revalidated": True}}
            ref = "P01:" + original["claims"][0]["claim_id"]
            prose = ("Synthetic report fixture checks source resolution only, not any financial conclusion. " * 4) + f"[{ref}]"
            report = {"title": "Synthetic convergence report", "narrative_markdown": prose}
            writer = NativeFixtureModel(marker="writer", replies=[
                [call("read_current_workpaper", {"paper_id": "P99"}, "bad"), call("research_artifact_catalog", {}, "catalog"),
                 call("get_research_method", {"method_id": "writer"}, "method")],
                [call("read_current_workpaper", {"paper_id": "P01"}, "read")],
                [call("submit_case_report", {"report": report}, "submit")]])
            agents["writer"] = build_case_output_agent(role="writer", model=writer, tools=tools, artifacts=artifacts, limits=limits, report_revision=reuse == "report")
            review = {"summary": "Synthetic final review checks graph sequencing and source contracts only, never economic truth.",
                "findings": ([{"finding_id": "F1", "severity": "material", "report_quote": "Synthetic report fixture",
                    "diagnosis": "Synthetic negative must remain visible as needs revision.",
                    "requested_change": "Synthetic finding only; do not claim actual financial review."}] if material else []),
                "unresolved_data_requests": []}
            model = NativeFixtureModel(marker="verifier", replies=[[call("submit_report_review", {"review": {**review, "completion": "complete"}}, "review")]])
            agents["verifier"] = build_case_output_agent(role="verifier", model=model, tools=tools, artifacts=artifacts, limits=limits)
            saver = InMemorySaver()
            graph = build_case_convergence_graph(agents=agents, artifacts=artifacts, question="fixture only", feedback=feedback,
                run_id="run", run_invocation_id="invoke", reused_revisions=reused,
                report_revision_request={"human_feedback": "unique prior report feedback fixture"} if reuse == "report" else None).compile(checkpointer=saver)
            assert len(list(graph.get_subgraphs())) == 8
            state = await graph.ainvoke({"run_id": "run", "run_invocation_id": "invoke"},
                {"configurable": {"thread_id": "case"}, "recursion_limit": 100})
            assert len(state["revisions"]) == 6
            assert state["phase"] == ("case_report_needs_revision" if material else "case_report_ready_for_human_review")
            assert ref in state["report"]["citations"]
            verifier_input = json.loads(model.contexts[0][1].content)
            assert "Not separately disclosed does not mean not achieved" in model.contexts[0][0].content
            assert verifier_input["report"] == report
            assert "citations" not in verifier_input["report"]
            assert "reasoning_content" not in json.dumps(state)
            assert artifacts.read_paper("P01") == original
            assert all("read_research_artifact" not in names for names in writer.seen)
            catalog = next(m for m in writer.contexts[1] if isinstance(m, ToolMessage) and m.name == "research_artifact_catalog")
            assert "Synthetic corrected current thesis for fixture paper P01" in catalog.content
            method = next(m for m in writer.contexts[1] if isinstance(m, ToolMessage) and m.name == "get_research_method")
            assert method.artifact["method_id"] == "writer" and "局部编辑" in method.artifact["content"]
            assert "get_research_method" in writer.contexts[0][0].content
            for pid in PAPERS:
                metrics = state["actor_metrics"]["author_"+pid]
                assert metrics["model_calls"] == (0 if pid in reused else 2)
                if pid in reused:
                    assert metrics["tool_calls"] == 0 and metrics["reused_from"] == reused[pid]["origin"]
            if reuse == "report":
                assert "unique prior report feedback fixture" in writer.contexts[0][1].content
                assert "unique prior report feedback fixture" not in str(model.contexts)
            checkpoints = list(saver.list(None))
            for actor in agents:
                rows = [c for c in checkpoints if c.config["configurable"].get("checkpoint_ns", "").startswith(actor+":")]
                assert rows
                last = max(rows, key=lambda c: len(c.checkpoint["channel_values"].get("messages", [])))
                messages = last.checkpoint["channel_values"]["messages"]
                marker = actor.removeprefix("author_")
                assert all(m.additional_kwargs["reasoning_content"] == marker for m in messages if isinstance(m, AIMessage))
    asyncio.run(run())


@pytest.mark.parametrize("mixed", [False, True])
def test_invalid_json_feedback_native_SDK_preserves_raw_call_and_valid_siblings(artifacts, mixed):
    import httpx
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
    revision = revision_fixture(artifacts, "P07")
    good = json.dumps({"revision": revision})
    bad = good + "}"  # Same earliest P07 A1 defect: extra JSON data.
    requests = []
    def serve(request):
        body = json.loads(request.content)
        turn = len(requests)
        requests.append(body)
        if turn:
            prior = next(m for m in body["messages"] if m["role"] == "assistant")
            assert prior["reasoning_content"] == "private native fixture, not a public rationale"
            assert next(c for c in prior["tool_calls"] if c["id"] == "invalid-submit")["function"]["arguments"] == bad
            results = [m for m in body["messages"] if m["role"] == "tool"]
            assert len(results) == 1 + mixed
            error = next(m for m in results if m["tool_call_id"] == "invalid-submit")
            assert "Extra data" in error["content"] and len(error["content"]) < 600
        calls = [{"id": "invalid-submit" if not turn else "valid-submit", "type": "function",
            "function": {"name": "submit_paper_revision", "arguments": bad if not turn else good}}]
        if mixed and not turn:
            calls.append({"id": "valid-read", "type": "function", "function": {
                "name": "read_research_artifact", "arguments": json.dumps({"paper_id": "P07"})}})
        return httpx.Response(200, json={"id": "fixture", "object": "chat.completion", "created": 1,
            "model": "deepseek-v4-pro", "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": "", "reasoning_content": "private native fixture, not a public rationale", "tool_calls": calls}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}})
    async def run():
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client, httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http:
            model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("fixture-not-secret"),
                http_async_client=http, max_retries=0, streaming=False)
            agent = build_case_output_agent(role="repair", model=model, tools=await case_mcp_tools(client),
                artifacts=artifacts, feedback=[{"finding_id": "fixture"}], paper_id="P07", limits={"model_calls": 2, "tool_calls": 4})
            result = await agent.ainvoke({"messages": [{"role": "user", "content": "Fixture only"}]})
            assert result["output"]["paper_id"] == "P07"
            first = next(m for m in result["messages"] if isinstance(m, AIMessage))
            assert first.invalid_tool_calls[0]["args"] == bad
            assert len(requests) == 2
    asyncio.run(run())


def test_real_P07_A1_counterexample_stays_invalid_and_is_pairable():
    from pathlib import Path
    from sec_agent.agent_runtime.dell_case_review_agent import InvalidToolCallFeedback
    path = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260906-dell-case-convergence-a1/model-context-reasoning.private.jsonl")
    if not path.exists():
        pytest.skip("private real run fixture not present")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    raw = next(r["raw_response"] for r in reversed(rows) if r.get("actor") == "author_P07" and r.get("event") == "response")
    message = AIMessage.model_validate(raw)
    result = InvalidToolCallFeedback().after_model({"messages": [message]}, None)
    assert result["jump_to"] == "model" and len(result["messages"]) == 1
    assert result["messages"][0].tool_call_id == message.invalid_tool_calls[0]["id"]
    detail = json.loads(result["messages"][0].content)
    assert detail["reason"] == "Extra data" and detail["column"] == 10935
    assert message.tool_calls == []  # Never auto-repair/execute invalid arguments.


@pytest.mark.parametrize('unknown_source', [False, True])
def test_report_extra_brace_uses_normal_native_source_validation_without_model_rewrite(artifacts, unknown_source):
    import httpx
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
    from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
    ref = 'P01:UNKNOWN' if unknown_source else 'P01:' + artifacts.read_paper('P01')['claims'][0]['claim_id']
    report = {'title': 'Report syntax recovery fixture', 'narrative_markdown': 'Public report candidate. '*12 + f'[{ref}]', 'charts': []}
    arguments = json.dumps({'report': report}) + '}'
    calls = []
    def serve(request):
        calls.append(request)
        return httpx.Response(200, json={'id': 'fixture', 'object': 'chat.completion', 'created': 1,
            'model': 'deepseek-v4-pro', 'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {
                'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'report-submit', 'type': 'function',
                    'function': {'name': 'submit_case_report', 'arguments': arguments}}]}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http:
            model = ReasoningPreservingChatDeepSeek(model='deepseek-v4-pro', api_key=SecretStr('fixture-not-secret'),
                http_async_client=http, max_retries=0, streaming=False)
            agent = build_case_output_agent(role='writer', model=model, tools=[], artifacts=artifacts,
                limits={'model_calls': 1, 'tool_calls': 2})
            if unknown_source:
                with pytest.raises(ModelCallLimitExceededError):
                    await agent.ainvoke({'messages': [{'role': 'user', 'content': 'Fixture only'}]})
            else:
                result = await agent.ainvoke({'messages': [{'role': 'user', 'content': 'Fixture only'}]})
                assert result['output']['narrative_markdown'] == report['narrative_markdown']
                message = next(m for m in result['messages'] if isinstance(m, AIMessage))
                assert message.response_metadata['format_recovery'] == 'redundant_closing_brace'
            assert len(calls) == 1
    asyncio.run(run())




def test_source_bound_updates_reject_quote_and_authority_errors_together(artifacts):
    data = revision_fixture(artifacts, "P01")
    source = next(s for s, row in artifacts.read_paper("P01", "sources").items() if row["result_state"] != "numeric_fact")
    data["claim_updates"] = [{"claim_id": "bad", "kind": "numeric_fact", "materiality": "high", "statement": "Synthetic incorrect authority claim.",
        "source_ids": [source], "numeric_authority": "authoritative", "citation_quotes": {source: "not the source text"}}]
    with pytest.raises(ValueError) as caught:
        validated_revision(PaperRevision.model_validate(data), paper_id="P01", feedback=[{"finding_id": "fixture"}], artifacts=artifacts, messages=[])
    assert "source_quote_not_exact" in str(caught.value)
    assert "claim_kind_or_authority_invalid" in str(caught.value)


def test_current_projection_keeps_unchanged_claims_and_citation_refs(artifacts):
    data = revision_fixture(artifacts, "P01")
    data["thesis"] = "Synthetic replacement thesis for projection-only verification."
    original = artifacts.read_paper("P01")
    row = validated_revision(PaperRevision.model_validate(data), paper_id="P01", feedback=[{"finding_id": "fixture"}], artifacts=artifacts, messages=[])
    current = artifacts.with_revisions({"P01": row})
    assert current.read_paper("P01")["thesis"] == data["thesis"]
    assert current.read_paper("P01")["claims"] == original["claims"]
    assert artifacts.read_paper("P01") == original
    with pytest.raises(ValueError, match="citation_ids"):
        report_citations(CaseReport(title="Synthetic report", narrative_markdown="test "*60+"[P01:missing]"), current)


def test_schema_only_convergence_reads_no_data_or_credentials(monkeypatch):
    import sec_agent.agent_runtime.dell_agent_server_entry as entry
    monkeypatch.setenv("FINSIGHT_DELL_SERVING_MODE", "case_convergence_v1")
    monkeypatch.setattr(entry, "open_case_review_composition", lambda **kwargs: pytest.fail("opened resources"))
    async def run():
        async with entry.dell_reference_vertical_graph({}, SimpleNamespace(execution_runtime=None)) as graph:
            assert len(list(graph.get_subgraphs())) == 8
            assert "report" in graph.get_output_jsonschema()["properties"]
    asyncio.run(run())








@pytest.mark.parametrize("author_count", [0, 1, 3])
def test_dynamic_author_counts_preserve_report_artifacts_without_model_context_duplication(artifacts, author_count):
    from langchain_core.runnables import RunnableLambda

    captured = {}
    selected = PAPERS[:author_count]
    report = {"title": "Dynamic graph fixture", "narrative_markdown": "Synthetic prose only. " * 20,
              "citations": {"fixture": {"text": "large-source-marker " * 10000}}}
    review = {"summary": "Synthetic graph sequencing only; not a financial review.", "findings": [], "unresolved_data_requests": []}

    def actor_result(state, actor):
        captured[actor] = json.loads(state["messages"][0].content)
        if actor.startswith("author_"):
            output = {"paper_id": actor.removeprefix("author_"), "finding_responses": []}
        else:
            output = report if actor == "writer" else review
        return {**state, "output": output}

    # Empty amendments suffice for this graph-only fixture; actual financial
    # submission validation is exercised by the native-agent tests above.
    view = SimpleNamespace(research_as_of=artifacts.research_as_of,
        read_paper=artifacts.read_paper,
        with_revisions=lambda revisions: SimpleNamespace(catalog=artifacts.catalog))
    actors = [*("author_" + pid for pid in selected), "writer", "verifier"]
    agents = {name: RunnableLambda(lambda state, name=name: actor_result(state, name)) for name in actors}
    graph = build_case_convergence_graph(agents=agents, artifacts=view, question="Fresh question fixture",
        feedback={pid: [] for pid in selected}, run_id="dynamic", run_invocation_id="fresh").compile()
    result = graph.invoke({"run_id": "dynamic", "run_invocation_id": "fresh"})
    assert result["phase"] == "case_report_ready_for_human_review"
    assert set(result.get("revisions", {})) == set(selected)
    assert result["report"] == report
    assert captured["verifier"]["report"] == {key: report[key] for key in ("title", "narrative_markdown")}
    assert "large-source-marker" not in json.dumps(captured)
    for pid in selected:
        author_seed = captured["author_" + pid]
        assert author_seed["original_workpaper"] == artifacts.read_paper(pid)
        assert "sources" not in author_seed
        assert "read_current_source" in author_seed["source_access"]
