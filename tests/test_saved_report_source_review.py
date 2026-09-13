import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage

from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent
from test_dell_case_convergence_agent import NativeFixtureModel
from test_dell_case_review_agent import call


def test_report_observations_are_isolated_and_do_not_create_research_papers():
    source = {"NUMFACT::fixture": {"numeric_fact_id": "NUMFACT::fixture", "result_state": "numeric_fact",
        "ticker": "FIX", "metric_id": "net_income", "value_decimal": "12", "unit": "USD",
        "period_end": "2025-12-31", "numeric_fact_authority": True}}
    original = deepcopy(source)
    artifacts = DellCaseArtifacts.from_observed_sources(source, case_id="test", research_as_of="2026-01-01")
    source["NUMFACT::fixture"]["value_decimal"] = "999"
    assert artifacts.catalog()["papers"] == []
    assert artifacts.read_source("NUMFACT::fixture")["value_decimal"] == "12"
    assert artifacts.search_sources('"net_income"')["matches"]
    with pytest.raises(ValueError, match="unknown_paper"):
        artifacts.read_paper("P01")
    with pytest.raises(ValueError, match="identity_invalid"):
        DellCaseArtifacts.from_observed_sources({"invented": original["NUMFACT::fixture"]}, case_id="x", research_as_of="x")


def test_existing_verifier_and_local_writer_can_use_saved_direct_report_sources():
    async def run():
        ref = "NUMFACT::fixture"
        source = {"numeric_fact_id": ref, "source_id": ref, "result_state": "numeric_fact", "ticker": "FIX",
            "metric_id": "net_income", "value_decimal": "12", "unit": "USD", "period_end": "2025-12-31",
            "numeric_fact_authority": True}
        artifacts = DellCaseArtifacts.from_observed_sources({ref: source}, case_id="test", research_as_of="2026-01-01")
        text = "Scope and source fixture. " * 12 + f"Operating profit 12 [{ref}]."
        report = {"title": "Saved report fixture", "narrative_markdown": text, "citations": {ref: {"sources": [source]}}}
        original = deepcopy(report)
        review = {"completion": "complete", "summary": "Source says net income, whereas this sentence incorrectly names operating profit. Other claims are outside this fixture.",
            "unresolved_data_requests": [], "findings": [{"finding_id": "F1", "severity": "material", "report_quote": "Operating profit 12",
            "diagnosis": "The bound source is net income, not operating profit.", "requested_change": "Use net income for the source metric and preserve its value.",
            "responsibility": "writer", "paper_ids": []}]}
        model = NativeFixtureModel(marker="saved-review", replies=[
            [call("read_current_source", {"source_id": ref}, "read")],
            [call("submit_report_review", {"review": review}, "submit")]])
        agent = build_case_output_agent(role="verifier", model=model, tools=[], artifacts=artifacts,
            require_responsibility=True, limits={"model_calls": 2, "tool_calls": 2})
        result = await agent.ainvoke({"report": report, "messages": [{"role": "user", "content": text}]})
        assert result["output"]["findings"][0]["responsibility"] == "writer"
        read = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "read_current_source")
        assert json.loads(read.content)["citation_status"] == "bound"
        model = NativeFixtureModel(marker="saved-writer", replies=[
            [call("submit_report_edits", {"edits": [{"old_str": "Operating profit 12", "new_str": "Net income 12"}]}, "edit")]])
        agent = build_case_output_agent(role="writer", model=model, tools=[], artifacts=artifacts,
            report_revision=True, limits={"model_calls": 1, "tool_calls": 1})
        result = await agent.ainvoke({"report": report, "request_action": "revise", "messages": [{"role": "user", "content": text}]})
        assert result["output"]["narrative_markdown"] == text.replace("Operating profit", "Net income")
        assert result["output"]["citations"] == report["citations"]
        assert report == original
    asyncio.run(run())






def test_selected_claim_role_consumes_scope_without_whole_report_obligations():
    async def run():
        artifacts = DellCaseArtifacts.from_observed_sources({}, case_id="fixture", research_as_of="2026-01-01")
        model = NativeFixtureModel(marker="focused", replies=[[call("submit_report_review", {"review": {
            "summary": "T1: The selected claim is a valid evidence limitation. This fixture exercises scoped completion only, not whole-report acceptance.",
            "completion": "complete", "unresolved_data_requests": [], "findings": []}}, "done")]])
        agent = build_case_output_agent(role="verifier", model=model, tools=[], artifacts=artifacts,
            review_scope="selected_claims", require_responsibility=True, method_instructions="Role method fixture.",
            limits={"model_calls": 1, "tool_calls": 1})
        result = await agent.ainvoke({"report": {"title": "Test title", "narrative_markdown": "Original paragraph. " * 15},
            "messages": [{"role": "user", "content": "Review selected T1 only."}]})
        assert result["output"]["unresolved_data_requests"] == []
        assert result["output"]["review_scope"] == "selected_claims"
        assert result["output"]["completion"] == "complete"
        assert result["output"]["full_report_acceptance"] is False
        system = str(model.contexts[0][0].content)
        assert "Invocation scope: selected claims only" in system
        assert "Check the opening thesis, headings" not in system
        assert "research_artifact_catalog" not in model.seen[0]
        assert "read_current_source" in model.seen[0]
    asyncio.run(run())
