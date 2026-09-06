"""Real MCP/native-loop source wiring; synthetic prose is not financial gold."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json

from langchain_core.messages import HumanMessage, ToolMessage
from mcp import Client
import pytest

from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
from sec_agent.agent_runtime.dell_case_convergence_agent import (
    answer_citations, build_case_output_agent, observed_sources,
)
from sec_agent.agent_runtime.dell_case_review_agent import case_mcp_tools
from sec_agent.research_foundation.source_document_navigation import navigate_source_nodes
from test_dell_case_convergence_agent import NativeFixtureModel
from test_dell_case_review_agent import artifacts, call
from test_dell_research_mcp import _build_server, _method_arguments


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
            ("read_source_document", "success", "search"), ("invented_tool", "success", "read")]:
        messages = [ToolMessage(content="ignored", tool_call_id="test", name=name, status=status,
                                artifact={"operation": operation, "items": [item]})]
        assert observed_sources(messages) == {}
        with pytest.raises(ValueError, match="not_observed"):
            answer_citations(f"Unobserved [{PASSAGE_ID}]", artifacts, messages)


@pytest.mark.local_data_integration
def test_specialist_native_calculator_survives_cross_agent_artifact_projection():
    from test_dell_specialist_agentic_composition import _RealMCPFakeModel, RUNTIME_ENVIRONMENT, _assert_assets
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    from sec_agent.agent_runtime.deepseek_structured_agents import _NATIVE_SPECIALIST_TOOLS
    _assert_assets()
    base, decisions = _RealMCPFakeModel(), []
    tool_names = {model.model_fields["action"].annotation.__args__[0]: name for name, model in _NATIVE_SPECIALIST_TOOLS.items()}

    def model(request):
        action = base(request)
        if action["action"] == "submit_workpaper":
            calculations = [item for obs in request["notebook"]["observations"] for item in obs["content"]
                            if item.get("calculation_id")]
            if not calculations:
                fact_id = next(c["fact_ids"][0] for c in action["claims"] if c["kind"] == "numeric_fact")
                action = {"action": "request_calculation", "context_digest": request["context_digest"],
                    "reason_summary": "Test existing calculator via the real MCP, not model-generated arithmetic.",
                    "request": {"expression": "a / 2", "operands": {"a": {"source_id": fact_id}},
                        "result_unit": "half_original_USD_fixture", "rationale": "Fixture only, not economic analysis."}}
            else:
                calc = calculations[0]
                action["claims"].append({"claim_id": "fixture:calculation", "kind": "calculation", "materiality": "low",
                    "statement": "Synthetic half-value calculation for source-wire testing only.", "evidence_ids": [],
                    "fact_ids": [calc["calculation_id"]], "numeric_authority": "non_authoritative",
                    "authority_note": calc["authority_note"], "reasoning_summary": "Test fixture, not a financial finding.", "citation_quotes": {}})
        decisions.append(action)
        return {"action": "native_tool_batch", "context_digest": request["context_digest"], "tool_calls": [
            {"id": f"native-fixture-{len(decisions)}", "name": tool_names[action["action"]], "args": action, "type": "tool_call"}]}

    with open_dell_specialist_scripted_qualification_composition(run_id="source-calculation-native-fixture",
            run_invocation_id="source-calculation-native-fixture-a1", branch_id=BRANCH,
            environment=RUNTIME_ENVIRONMENT, scripted_model_turn=model, max_model_turns=8) as composition:
        result = composition.graph.invoke(composition.graph_input.model_dump(mode="json"), {"recursion_limit": 40})
    assert result["final_submission"] is not None
    assert [d["action"] for d in decisions].count("request_calculation") == 1
    current = DellCaseArtifacts([result])
    claim = next(c for c in current.read_paper("P01", "claims") if c["kind"] == "calculation")
    value = current.read_source(claim["source_ids"][0])
    assert value["arithmetic_verified"] is True and value["numeric_fact_authority"] is False
    detail = json.loads(value["text"])
    original_id = detail["operands"]["a"]["source_id"]
    assert current.read_source(detail["operand_source_aliases"][original_id])["numeric_fact_authority"] is True
    assert answer_citations("Fixture [P01:fixture:calculation]", current, [])["P01:fixture:calculation"]["sources"]


@pytest.mark.local_data_integration
@pytest.mark.parametrize("ticker,available", [("NVDA", True), ("HPE", False)])
def test_specialist_peer_sql_queries_are_not_rejected_as_outside_dell(ticker, available):
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT, _assert_assets
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    _assert_assets()
    requests = []
    def model(request):
        requests.append(request)
        if len(requests) == 1:
            return {"action": "request_finance", "context_digest": request["context_digest"], "reason_summary": "Host peer SQL qualification.",
                    "intent": {"ticker": ticker, "metric_ids": ["revenue"], "granularity": "quarter_discrete", "selection_mode": "latest_on_or_before"}}
        return {"action": "request_human_review", "context_digest": request["context_digest"],
                "reason_summary": "Host-only tool qualification complete.", "blocker_code": "fixture_complete"}
    with open_dell_specialist_scripted_qualification_composition(run_id="peer-sql-fixture",
            run_invocation_id="peer-sql-fixture-a1", branch_id="Q8_COMPETITION_VALUE_POOL",
            environment=RUNTIME_ENVIRONMENT, scripted_model_turn=model) as composition:
        result = composition.graph.invoke(composition.graph_input.model_dump(mode="json"), {"recursion_limit": 20})
    items = [item for obs in result["notebook"]["observations"] for item in obs["content"]]
    facts = [item for item in items if item.get("result_state") == "numeric_fact"]
    if available:
        assert facts and all(f["ticker"] == ticker and f["numeric_fact_authority"] is True for f in facts)
    else:
        # The current frozen mart contains DELL/MU/NVDA, not HPE. This is a
        # truthful data-coverage gap, not a ticker permission error/public gap.
        assert not facts and any(i.get("typed_gap", {}).get("gap_code") == "typed_fact_not_found_for_as_of_and_period" for i in items)
        assert all(obs["failure"] is None for obs in result["notebook"]["observations"])


@pytest.mark.local_data_integration
def test_actual_local_hpe_pdf_window_calculates_without_pretending_sql_authority():
    """Host-read development check of a real parsed page, not a model answer seed."""
    from decimal import Decimal
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT
    from sec_agent.agent_runtime.dell_agent_server_data_composition import (
        open_dell_approved_data_composition, DELL_APPROVED_RESEARCH_AS_OF, DELL_APPROVED_DATA_SNAPSHOT_ID)
    async def run():
        attempt = "local-hpe-source-calculator-fixture-a1"
        with open_dell_approved_data_composition(run_invocation_id=attempt, environment=RUNTIME_ENVIRONMENT,
                source_read_enabled=True) as composition:
            async with Client(composition.mcp_server, raise_exceptions=False) as client:
                method = await client.call_tool("get_dell_research_method", {"branch_ids": [BRANCH],
                    "research_as_of": DELL_APPROVED_RESEARCH_AS_OF, "data_snapshot_id": DELL_APPROVED_DATA_SNAPSHOT_ID,
                    "execution_attempt_id": attempt})
                read = await client.call_tool("read_source_document", {"branch_id": BRANCH, "run_scope": method.structured_content["run_scope"],
                    "request": {"operation": "read", "document_id": "DOC::CFF8E63F4B9BE4912F4138DA", "node_id": "CHUNK::8570D626593572A0828C15E8"}})
                assert not read.is_error
                page = read.structured_content["items"][0]
                assert page["parser_page_start"] == 8 and page["ticker"] == "HPE"
                assert "April 30, 2026 January 31, 2026 April 30, 2025" in page["passage"]
                assert "GAAP gross profit margin 36.5 % 35.9 % 28.4 %" in page["passage"]
                calculated = await client.call_tool("calculate_research_metric", {"request": {"expression": "profit / revenue * 100",
                    "operands": {"profit": {"source_id": page["passage_id"], "literal": "3,900", "quote": "GAAP gross profit 3,900 3,340 2,169"},
                                 "revenue": {"source_id": page["passage_id"], "literal": "10,678", "quote": "GAAP net revenue $ 10,678 $ 9,301 $ 7,627"}},
                    "result_unit": "percent", "rationale": "Host development check: first column, three months ended April 30 2026; both inputs in millions. Parsed PDF, not S2 facts."}})
                assert not calculated.is_error, calculated.content
                result = calculated.structured_content
                assert Decimal(result["value_decimal"]).quantize(Decimal("0.1")) == Decimal("36.5")
                assert not result["numeric_fact_authority"] and not result["financial_semantics_verified"]
                assert all(x["authority"] == "non_authoritative_source_reported" for x in result["operands"].values())
                assert all(x["source_provenance"]["source_locator"]["node_id"] == page["node_id"] for x in result["operands"].values())
    asyncio.run(run())
