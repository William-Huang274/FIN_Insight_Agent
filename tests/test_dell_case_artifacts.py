"""Real archived handoff qualification + deterministic calculator counterexamples."""
import asyncio
from copy import deepcopy
from decimal import Decimal
import json

import pytest

from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources


def _lookup(source_id):
    fixtures = {
        "fact": {"result_state": "numeric_fact", "numeric_fact_authority": True, "value_decimal": "100", "unit": "USD"},
        "text": {"result_state": "source_bound_passage", "writer_citable": True, "passage": "Fixture: revenue was 1,234.50 dollars, not actual company data."},
        "candidate": {"result_state": "retrieval_candidate", "value_decimal": "100"},
    }
    if source_id not in fixtures:
        raise ValueError("unknown_source")
    return fixtures[source_id]


def _calculate(expression="a / 2", operands=None):
    request = SourceBoundCalculation(expression=expression, operands=operands or {"a": {"source_id": "fact"}},
        result_unit="test_unit", rationale="Fixture arithmetic, not a financial conclusion.")
    return calculate_from_sources(request, _lookup)


def test_calculator_reads_s2_value_locally_without_model_copy_or_authority_promotion():
    result = _calculate()
    assert result["value_decimal"] == "50" and result["arithmetic_verified"]
    assert not result["numeric_fact_authority"] and not result["financial_semantics_verified"]
    assert result["operands"]["a"]["authority"] == "s2_input"
    assert result["result_state"] == "non_authoritative_metric"


def test_calculator_non_s2_source_literal_and_assumption_are_explicit():
    result = _calculate("a * scale", {"a": {"source_id": "text", "literal": "1,234.50", "quote": "revenue was 1,234.50 dollars"},
        "scale": {"literal": "0.1", "assumption_note": "Illustrative scenario, not issuer guidance"}})
    assert Decimal(result["value_decimal"]) == Decimal("123.450")
    assert result["operands"]["a"]["authority"] == "non_authoritative_source_reported"
    assert not result["operands"]["a"]["extraction_meaning_verified"]
    assert result["operands"]["scale"]["authority"] == "assumption"


@pytest.mark.parametrize("operands,error", [
    ({"a": {"source_id": "fact", "literal": "101"}}, "differs_from_observed"),
    ({"a": {"source_id": "missing"}}, "unknown_source"),
    ({"a": {"source_id": "candidate"}}, "requires_observed"),
    ({"a": {"source_id": "text", "literal": "234.50", "quote": "revenue was 1,234.50 dollars"}}, "literal_not_in_exact"),
    ({"a": {"source_id": "text", "literal": "1,234.50", "quote": "made-up source"}}, "quote_not_in_observed"),
    ({"a": {"literal": "5"}}, "explicit_assumption"),
    ({"a": {"literal": "1e100000", "assumption_note": "fixture"}}, "plain_decimal"),
])
def test_calculator_rejects_unbound_wrong_or_unlabelled_inputs(operands, error):
    with pytest.raises(ValueError, match=error):
        _calculate(operands=operands)


@pytest.mark.parametrize("expression", [
    "a / 0", "a ** (9 ** 9)", "a.__class__", "a.as_tuple()", "__import__('os').getcwd()",
    "a; 2", "a = 2", "[a]", "'x' * a", "a << 1000000", "a + 0.2", "(lambda: a)()", "b + a", "100",
])
def test_calculator_rejects_code_dos_unknown_and_unrelated_source_bindings(expression):
    with pytest.raises(ValueError):
        _calculate(expression)


@pytest.fixture(scope="module")
def real_bundle():
    from scripts.qualification.dell_q1_specialist_paid_shadow.collect_research_bundle import SOURCES, collect
    if not all(path.is_file() for path, _ in SOURCES):
        pytest.skip("local immutable research artifacts unavailable")
    return collect()


def test_real_nine_topics_and_ten_unchanged_papers_keep_parent_failure(real_bundle):
    artifacts = DellCaseArtifacts(real_bundle["papers"])
    assert len(artifacts.catalog()["papers"]) == 10
    assert len({p["branch_id"] for p in artifacts.catalog()["papers"]}) == 9
    assert not real_bundle["financial_or_product_pass"]
    assert any(o["source_role"] == "accepted_children_of_failed_parent" for o in real_bundle["origins"])
    original = deepcopy(real_bundle)
    for p in artifacts.catalog()["papers"]:
        view = artifacts.read_paper(p["paper_id"])
        assert "context_digest" not in view and "notebook" not in view
        for claim in view["claims"]:
            for source_id in claim["source_ids"]:
                source = artifacts.read_source(source_id)
                assert source.get("text") or source.get("value_decimal") is not None
                assert "mcp_receipt_chain" not in source
        view["thesis"] = "caller edit cannot mutate source"
        assert artifacts.read_paper(p["paper_id"])["thesis"] != view["thesis"]
    assert real_bundle == original
    with pytest.raises(ValueError, match="duplicate_paper"):
        DellCaseArtifacts([real_bundle["papers"][0], real_bundle["papers"][0]])


def test_mcp_actual_client_reads_one_source_and_calculates_from_real_s2_fact(real_bundle):
    from mcp import Client
    from test_dell_research_mcp import _build_server
    artifacts = DellCaseArtifacts(real_bundle["papers"])
    server = _build_server(case_artifacts=artifacts)

    async def exercise():
        async with Client(server) as client:
            catalog = await client.call_tool("research_artifact_catalog", {})
            assert not catalog.is_error
            paper = await client.call_tool("read_research_artifact", {"paper_id": "P01", "section": "sources"})
            assert not paper.is_error
            sources = artifacts.read_paper("P01", "sources")
            source_id = next(key for key in sources if sources[key]["result_state"] == "numeric_fact")
            source = await client.call_tool("read_research_source", {"source_id": source_id})
            assert not source.is_error
            result = await client.call_tool("calculate_research_metric", {"request": {
                "expression": "a / 2", "operands": {"a": {"source_id": source_id}},
                "result_unit": "test_half_original_unit", "rationale": "Host transport/arithmetic check, no financial claim."}})
            assert not result.is_error
            # Actual FY2026 source inputs -> locally recomputed margin, compared
            # with the existing independent S2 derived metric (not model gold).
            by_metric = {item["metric_id"]: key for key, item in artifacts.read_paper("P09", "sources").items()
                         if item["result_state"] == "numeric_fact" and item.get("fiscal_year") == 2026}
            margin = await client.call_tool("calculate_research_metric", {"request": {
                "expression": "gross_profit / revenue * 100", "operands": {
                    "gross_profit": {"source_id": by_metric["gross_profit"]}, "revenue": {"source_id": by_metric["revenue"]}},
                "result_unit": "percent", "rationale": "Host F_MARGIN check on same-period DELL FY2026 S2 inputs."}})
            assert not margin.is_error
            expected = Decimal(artifacts.source_item(by_metric["gross_margin"])["value_decimal"])
            assert Decimal(margin.structured_content["value_decimal"]) == expected
            bad = await client.call_tool("read_research_source", {"source_id": "D:/secrets"})
            assert bad.is_error
    asyncio.run(exercise())


@pytest.mark.local_data_integration
def test_live_sql_ids_calculate_only_after_observation_in_this_composition(real_bundle):
    """Actual read-only Dell mart through MCP, not fabricated NumericFact IDs."""
    from mcp import Client
    from test_dell_agent_server_data_composition import DEFAULT_ARTIFACT_ENV
    from sec_agent.agent_runtime.dell_agent_server_data_composition import (
        open_dell_approved_data_composition, DELL_APPROVED_RESEARCH_AS_OF, DELL_APPROVED_DATA_SNAPSHOT_ID)

    artifacts = DellCaseArtifacts(real_bundle["papers"])
    async def exercise():
        branch = artifacts.catalog()["papers"][0]["branch_id"]
        calculation = None
        for index in range(2):
            attempt = f"host-sql-calculator-binding-{index}"
            with open_dell_approved_data_composition(run_invocation_id=attempt,
                    environment=DEFAULT_ARTIFACT_ENV, case_artifacts=artifacts) as composition:
                async with Client(composition.mcp_server, raise_exceptions=False) as client:
                    if calculation is not None:
                        unobserved = await client.call_tool("calculate_research_metric", {"request": calculation})
                        assert unobserved.is_error and "Re-query SQL" in str(unobserved.content)
                    method = await client.call_tool("get_dell_research_method", {
                        "branch_ids": [branch], "research_as_of": DELL_APPROVED_RESEARCH_AS_OF,
                        "data_snapshot_id": DELL_APPROVED_DATA_SNAPSHOT_ID, "execution_attempt_id": attempt})
                    assert not method.is_error
                    queried = await client.call_tool("query_company_financial_facts", {
                        "branch_id": branch, "run_scope": method.structured_content["run_scope"],
                        "ticker": "DELL", "metric_ids": ["revenue", "operating_income"],
                        "research_as_of": "2026-09-02", "granularity": "quarter_discrete",
                        "selection_mode": "exact_period_end", "period_end": "2026-05-01", "fiscal_years": [2027]})
                    assert not queried.is_error
                    query = queried.structured_content
                    assert query["resolved_metric_count"] == 2
                    assert query["fact_mart_sha256_before"] == query["fact_mart_sha256_after"]
                    facts = {r["metric_id"]: r["facts"][0] for r in query["results"]}
                    assert facts["revenue"]["value_decimal"] == "43842000000"
                    assert facts["operating_income"]["value_decimal"] == "3656000000"
                    calculation = {"expression": "operating_income / revenue * 100", "operands": {
                        k: {"source_id": f["numeric_fact_id"]} for k, f in facts.items()},
                        "result_unit": "percent", "rationale": "Host development check: same-company, same-quarter GAAP operating income / revenue. Not a model gold test."}
                    margin = await client.call_tool("calculate_research_metric", {"request": calculation})
                    assert not margin.is_error, margin.content
                    result = margin.structured_content
                    expected = Decimal(3656) / Decimal(43842) * 100
                    assert abs(Decimal(result["value_decimal"]) - expected) < Decimal("1e-20")
                    assert not result["numeric_fact_authority"] and result["arithmetic_verified"]
                    assert all(v["authority"] == "s2_input" and v["period_end"] == "2026-05-01"
                               for v in result["operands"].values())
                    from langchain_core.messages import ToolMessage
                    from sec_agent.agent_runtime.dell_case_convergence_agent import answer_citations
                    fact_id = facts["revenue"]["numeric_fact_id"]
                    refs = answer_citations(f"Read [{fact_id}], calculate [{result['calculation_id']}]", artifacts, [
                        ToolMessage(content="SQL", artifact=query, name="query_company_financial_facts", tool_call_id="query"),
                        ToolMessage(content="calculation", artifact=result, name="calculate_research_metric", tool_call_id="calc")])
                    assert refs[fact_id]["sources"][0]["value_decimal"] == "43842000000"
                    assert refs[result["calculation_id"]]["claim"]["numeric_authority"] == "non_authoritative"
                    assert len(refs[result["calculation_id"]]["sources"]) == 3
                    if index == 0:
                        # Full native query -> calculation -> accepted answer,
                        # with a scripted model but actual SQL/MCP/tool artifacts.
                        from langchain_core.messages import HumanMessage
                        from test_dell_case_convergence_agent import NativeFixtureModel
                        from test_dell_case_review_agent import call
                        from sec_agent.agent_runtime.dell_case_review_agent import case_mcp_tools
                        from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent
                        model = NativeFixtureModel(marker="host-fixture-only", replies=[
                            [call("query_company_financial_facts", {"branch_id": branch, **query["query"]}, "query-again")],
                            [call("calculate_research_metric", {"request": calculation}, "calc-again")],
                            [call("submit_case_answer", {"answer_markdown": f"Development fixture: source [{fact_id}], computed [{result['calculation_id']}]"}, "answer")]])
                        native_tools = await case_mcp_tools(client, run_scope=method.structured_content["run_scope"])
                        agent = build_case_output_agent(role="writer", model=model, tools=native_tools, artifacts=artifacts,
                            limits={"model_calls": 4, "tool_calls": 8}, allow_answers=True, answer_only=True)
                        accepted = await agent.ainvoke({"messages": [HumanMessage(content="Host protocol test, not semantic gold")], "request_action": "ask"})
                        assert accepted["output"]["kind"] == "answer" and len(model.contexts) == 3
                        assert accepted["output"]["citations"] == refs
                        # The report uses the same observed IDs, not an invented
                        # old workpaper claim. SQL/calculation stay real/read-only.
                        report = {"title": "Host integration fixture, not a research result",
                            "narrative_markdown": ("This is a mechanical source-binding development fixture, not a financial conclusion. " * 4)
                                + f"Source [{fact_id}], computed [{result['calculation_id']}]."}
                        writer = NativeFixtureModel(marker="report-fixture", replies=[
                            [call("query_company_financial_facts", {"branch_id": branch, **query["query"]}, "report-query")],
                            [call("calculate_research_metric", {"request": calculation}, "report-calc")],
                            [call("submit_case_report", {"report": report}, "report-submit")]])
                        writer_graph = build_case_output_agent(role="writer", model=writer, tools=native_tools,
                            artifacts=artifacts, limits={"model_calls": 4, "tool_calls": 8})
                        written = await writer_graph.ainvoke({"messages": [HumanMessage(content="Host report citation qualification only")]})
                        assert written["output"]["citations"] == refs
                        editor = NativeFixtureModel(marker="edit-fixture", replies=[
                            [call("read_current_source", {"source_id": result["calculation_id"]}, "read-citation")],
                            [call("submit_report_edits", {"edits": [{"old_str": "Source [", "new_str": "Unchanged cited source ["}]}, "edit")]])
                        edit_graph = build_case_output_agent(role="writer", model=editor, tools=native_tools,
                            artifacts=artifacts, limits={"model_calls": 3, "tool_calls": 6}, allow_answers=True)
                        edited = await edit_graph.ainvoke({"messages": [HumanMessage(content="Change only the fixture wording")],
                            "report": written["output"], "request_action": "revise"})
                        assert edited["output"]["citations"] == refs
                        assert "operating_income / revenue * 100" in str(editor.contexts[1])
                        assert "arithmetic" not in edited["output"]["narrative_markdown"].lower()
                    wrong = deepcopy(calculation)
                    wrong["operands"]["revenue"]["literal"] = "1"
                    rejected = await client.call_tool("calculate_research_metric", {"request": wrong})
                    assert rejected.is_error and "differs_from_observed_s2_fact" in str(rejected.content)
                    wrong["operands"]["revenue"] = {"source_id": "NUMFACT::made-up"}
                    rejected = await client.call_tool("calculate_research_metric", {"request": wrong})
                    assert rejected.is_error and "Re-query SQL" in str(rejected.content)
    asyncio.run(exercise())
