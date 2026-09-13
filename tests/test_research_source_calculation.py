"""Real MCP/native-loop source wiring; synthetic prose is not financial gold."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json

from langchain_core.messages import HumanMessage, ToolMessage
from mcp import Client
import pytest

from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.agent_runtime.report_synthesis_agent import (
    answer_citations, build_case_output_agent, observed_sources,
)
from sec_agent.agent_runtime.case_review_agent import case_mcp_tools
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest, navigate_source_nodes
from test_report_synthesis_agent import NativeFixtureModel
from test_case_review_agent import artifacts, call
from test_research_mcp import _build_server, _method_arguments


TEXT = "Synthetic test document: revenue was 1,234.50 dollars. This is a protocol fixture, not Dell data."
NODE = {"node_id": "fixture-node", "parent_document_id": "fixture-document", "node_kind": "section",
    "content": TEXT, "content_sha256": sha256(TEXT.encode()).hexdigest(),
    "stable_url": "https://example.com/protocol-fixture", "title": "Synthetic protocol fixture",
    "section_path": ["Results"], "document_kind": "html", "ticker": "FIXTURE", "publication_date": "2026-08-01"}
PASSAGE_ID = f"PASSAGE::{NODE['node_id']}::{NODE['content_sha256'][:16]}"
BRANCH = "Q1_ISSUER_TRUTH"
CALCULATION = {"expression": "amount / 2", "operands": {"amount": {"source_id": PASSAGE_ID,
    "literal": "1,234.50", "quote": "revenue was 1,234.50 dollars"}}, "result_unit": "fixture_dollars",
    "rationale": "Synthetic source arithmetic for a plumbing test, not a business conclusion."}


def source_reader(*, request, **_kwargs):
    return navigate_source_nodes([NODE], request, snapshot="frozen-fixture")


def test_read_passage_calculate_native_report_and_preserved_revision(artifacts):
    async def run():
        server = _build_server(case_artifacts=artifacts, source_document_reader=source_reader)
        async with Client(server, raise_exceptions=False) as client:
            method = await client.call_tool("get_dell_research_method", _method_arguments([BRANCH]))
            scope = method.structured_content["run_scope"]
            unobserved = await client.call_tool("calculate_research_metric", {"request": CALCULATION})
            assert unobserved.is_error
            await client.call_tool("read_source_document", {"request": {"operation": "catalog"}, "branch_id": BRANCH, "run_scope": scope})
            preview_only = await client.call_tool("calculate_research_metric", {"request": CALCULATION})
            assert preview_only.is_error
            read_args = {"request": {"operation": "read", "document_id": NODE["parent_document_id"]}, "branch_id": BRANCH}
            read = await client.call_tool("read_source_document", {**read_args, "run_scope": scope})
            assert not read.is_error
            result = await client.call_tool("calculate_research_metric", {"request": CALCULATION})
            assert not result.is_error, result.content
            calculation = result.structured_content
            assert calculation["value_decimal"] == "617.25" and not calculation["numeric_fact_authority"]
            operand = calculation["operands"]["amount"]
            assert operand["authority"] == "non_authoritative_source_reported"
            assert operand["source_provenance"]["source_url"] == NODE["stable_url"]
            assert operand["source_provenance"]["source_locator"]["node_id"] == NODE["node_id"]
            chained = await client.call_tool("calculate_research_metric", {"request": {
                "expression": "prior * 2", "operands": {"prior": {"source_id": calculation["calculation_id"]}},
                "result_unit": "fixture_dollars", "rationale": "Reuse the same MCP session's verified calculation; not financial validation."}})
            assert not chained.is_error, chained.content
            assert chained.structured_content["value_decimal"] == "1234.50"
            assert chained.structured_content["operands"]["prior"]["authority"] == "non_authoritative_calculation"
            wrong_quote = deepcopy(CALCULATION)
            wrong_quote["operands"]["amount"]["quote"] = "invented revenue was 1,234.50"
            assert (await client.call_tool("calculate_research_metric", {"request": wrong_quote})).is_error

            report = {"title": "Synthetic source-wire check", "narrative_markdown":
                "This source-bound protocol fixture tests the plumbing, not economic correctness. " * 4
                + f"Read [{PASSAGE_ID}] and calculate [{calculation['calculation_id']}]. Non-authoritative computation."}
            model = NativeFixtureModel(marker="source-wire-test", replies=[
                [call("read_source_document", read_args, "read")],
                [call("calculate_research_metric", {"request": CALCULATION}, "calculate")],
                [call("submit_case_report", {"report": report}, "report")]])
            agent = build_case_output_agent(role="writer", model=model, tools=await case_mcp_tools(client, run_scope=scope),
                artifacts=artifacts, limits={"model_calls": 4, "tool_calls": 6})
            outcome = await agent.ainvoke({"messages": [HumanMessage(content="Protocol test only")]})
            citations = outcome["output"]["citations"]
            assert set(citations) == {PASSAGE_ID, calculation["calculation_id"]}
            source = citations[PASSAGE_ID]["sources"][0]
            assert source["text"] == TEXT and source["source_locator"]["node_id"] == NODE["node_id"]
            assert source["numeric_fact_authority"] is False
            assert len(citations[calculation["calculation_id"]]["sources"]) == 2
            assert answer_citations(report["narrative_markdown"], artifacts, [], prior_citations=citations) == citations
            with pytest.raises(ValueError, match="not_observed"):
                answer_citations(report["narrative_markdown"], artifacts, [])

        # A new composition does not inherit another actor's observed source map.
        async with Client(_build_server(source_document_reader=source_reader), raise_exceptions=False) as other:
            assert (await other.call_tool("calculate_research_metric", {"request": CALCULATION})).is_error
    asyncio.run(run())


def test_failed_tools_model_text_and_search_previews_cannot_register_sources(artifacts):
    item = {"passage_id": PASSAGE_ID, "passage": TEXT, "result_state": "source_bound_passage",
            "writer_citable": True, "numeric_fact_authority": False}
    for name, status, operation in [("read_source_document", "error", "read"),
            ("invented_tool", "success", "read")]:
        messages = [ToolMessage(content="ignored", tool_call_id="test", name=name, status=status,
                                artifact={"operation": operation, "items": [item]})]
        assert observed_sources(messages) == {}
        with pytest.raises(ValueError, match="not_observed"):
            answer_citations(f"Unobserved [{PASSAGE_ID}]", artifacts, messages)
    # Use the real navigation preview contract. A saved, fully bound passage
    # returned by a knowledge search is not a preview merely because its outer
    # operation is "search" (supported since source-recovery 40fd7859).
    preview = navigate_source_nodes([{**NODE, "node_kind": "paragraph"}], SourceDocumentRequest(operation="search", query="revenue"),
        snapshot="frozen-fixture").model_dump(mode="json")
    assert preview["items"] and preview["items"][0]["writer_citable"] is False
    messages = [ToolMessage(content=json.dumps(preview), tool_call_id="preview", name="read_source_document", artifact=preview)]
    assert observed_sources(messages) == {}
    with pytest.raises(ValueError, match="not_observed"):
        answer_citations(f"Unobserved [{PASSAGE_ID}]", artifacts, messages)
    assert observed_sources([HumanMessage(content=json.dumps(item))]) == {}


def test_local_sql_gap_is_citable_as_query_receipt_not_financial_evidence(artifacts):
    ref = "MCPFACT::synthetic-local-gap"
    gap = {"authority_state": "s2_numeric_fact_query_result", "query_digest": "fixture-query",
        "query": {"ticker": "SYNTHETIC", "period_end": "2025-12-31"}, "results": [{
            "fact_request_id": ref, "status": "typed_gap", "facts": [],
            "typed_gap": {"gap_code": "typed_fact_not_found_for_as_of_and_period"}}]}
    observed = ToolMessage(content=json.dumps(gap), tool_call_id="fixture-call",
        name="query_company_financial_facts", artifact=gap)
    prose = f"指定期间本地未取得数值，不能推出发行人未披露 [{ref}]"
    citations = answer_citations(prose, artifacts, [observed])
    source = citations[ref]["sources"][0]
    assert source["result_state"] == "query_gap_receipt" and source["numeric_fact_authority"] is False
    assert json.loads(source["text"])["query"]["ticker"] == "SYNTHETIC"
    assert observed_sources([observed]) == {}  # Not a calculator operand or NumericFact.
    for bad in [[], [HumanMessage(content=json.dumps(gap))],
            [ToolMessage(content=json.dumps(gap), tool_call_id="failed", name=observed.name, artifact=gap, status="error")]]:
        with pytest.raises(ValueError, match="not_observed"):
            answer_citations(prose, artifacts, bad)

    async def run():
        model = NativeFixtureModel(marker="local-gap-answer", replies=[[
            call("submit_case_answer", {"answer_markdown": prose}, "submit")]])
        agent = build_case_output_agent(role="writer", model=model, tools=[], artifacts=artifacts,
            limits={"model_calls": 2, "tool_calls": 3}, allow_answers=True, answer_only=True)
        outcome = await agent.ainvoke({"report": {}, "request_action": "ask", "messages": [
            HumanMessage(content="Explain the observed local query gap"), observed]})
        assert outcome["output"]["citations"] == citations
    asyncio.run(run())


def test_followup_can_read_and_cite_persisted_calculation_without_recalculation(artifacts):
    from test_report_synthesis_agent import saved_calculation_chart
    report, _, calculation = saved_calculation_chart(artifacts)
    report.pop("charts")
    calc_id = calculation["calculation_id"]
    report["citations"] = answer_citations(f"Fixture [{calc_id}]", artifacts, [ToolMessage(
        content="synthetic calculation", name="calculate_research_metric", tool_call_id="prior", artifact=calculation)])
    original = deepcopy(report)
    async def run():
        model = NativeFixtureModel(marker="saved-answer", replies=[
            [call("read_current_source", {"source_id": calc_id}, "read")],
            [call("submit_case_answer", {"answer_markdown": f"Saved fixture calculation, not S2 authority [{calc_id}]"}, "submit")]])
        agent = build_case_output_agent(role="writer", model=model, tools=[], artifacts=artifacts,
            limits={"model_calls": 3, "tool_calls": 4}, allow_answers=True, answer_only=True)
        outcome = await agent.ainvoke({"report": report, "request_action": "ask",
            "messages": [HumanMessage(content="Read the saved calculation, don't regenerate the report.")]})
        assert outcome["output"]["citations"][calc_id] == report["citations"][calc_id]
        assert outcome["report"] == original and len(model.contexts) == 2
    asyncio.run(run())


def test_canonical_alias_lookup_rejects_same_id_with_different_observation(artifacts):
    current = deepcopy(artifacts)
    item = next(row for row in current._sources.values() if row.get("numeric_fact_id"))
    current._sources["P01:S999"] = {**item, "value_decimal": "-999999999999"}
    with pytest.raises(ValueError, match="canonical_source_observation_conflict"):
        current.source_item(item["numeric_fact_id"])


def test_followup_reuses_answer_only_calc_with_operands_outside_case_catalog(artifacts):
    from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources
    fact = {"result_state": "numeric_fact", "numeric_fact_authority": True,
        "value_decimal": "12", "ticker": "SYNTHETIC", "metric_id": "revenue",
        "unit": "USD", "period_end": "2025-12-31", "source_observation_ids": ["CFOBS::synthetic"]}
    calculation = calculate_from_sources(SourceBoundCalculation(expression="a / 2",
        operands={"a": {"source_id": "NUMFACT::synthetic"}}, result_unit="USD",
        rationale="Synthetic prior-answer fixture"), lambda _: fact)
    ref = calculation["calculation_id"]
    messages = [ToolMessage(content="fixture", tool_call_id="fact", name="query_company_financial_facts",
        artifact={"authority_state": "s2_numeric_fact_query_result", "results": [{"status": "resolved",
            "facts": [{**fact, "numeric_fact_id": "NUMFACT::synthetic"}]}]}),
        ToolMessage(content="fixture", tool_call_id="calc", name="calculate_research_metric", artifact=calculation)]
    citations = answer_citations(f"Fixture [{ref}]", artifacts, messages)
    with pytest.raises(ValueError, match="unknown_source_id"):
        artifacts.source_item("NUMFACT::synthetic")

    async def run():
        model = NativeFixtureModel(marker="prior-answer-only", replies=[
            [call("read_current_source", {"source_id": ref}, "read")],
            [call("submit_case_answer", {"answer_markdown": f"Saved synthetic calculation, non-authoritative [{ref}]"}, "submit")]])
        agent = build_case_output_agent(role="writer", model=model, tools=[], artifacts=artifacts,
            limits={"model_calls": 3, "tool_calls": 4}, allow_answers=True, answer_only=True)
        outcome = await agent.ainvoke({"report": {}, "request_action": "ask",
            "conversation": [{"role": "assistant", "content": "Prior fixture answer", "citations": citations}],
            "messages": [HumanMessage(content="Read the prior answer calculation without SQL or recalculation")]})
        assert outcome["output"]["citations"] == citations
        assert len(model.contexts) == 2
        assert outcome["report"] == {}
    asyncio.run(run())
