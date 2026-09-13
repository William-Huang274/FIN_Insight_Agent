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


def test_catalog_exposes_actual_claim_binding_and_rejects_guessed_number():
    from test_research_session import _new_worker_fixture
    from sec_agent.agent_runtime.dell_case_convergence_agent import report_citations
    paper = _new_worker_fixture()
    paper["final_submission"]["claims"][0]["claim_id"] = "revenue_period_boundary"
    artifacts = DellCaseArtifacts([paper])
    assert "P01:revenue_period_boundary" in artifacts.catalog()["papers"][0]["citation_ids"]
    with pytest.raises(ValueError, match="exact current citation IDs") as error:
        report_citations("An unsupported alias [P01:C999].", artifacts)
    assert "P01:revenue_period_boundary" in str(error.value)
    assert "P01:C999" not in artifacts.catalog()["papers"][0]["citation_ids"]


def test_answer_can_reference_exact_operand_source_alias_without_claim_renaming():
    from test_research_session import _new_worker_fixture
    from sec_agent.agent_runtime.dell_case_convergence_agent import answer_citations
    artifacts = DellCaseArtifacts([_new_worker_fixture()])
    ref = next(iter(artifacts.read_paper("P01", "sources")))
    before = deepcopy(artifacts._sources)
    bound = answer_citations(f"The saved calculation names this original source [{ref}].", artifacts, [])
    assert bound[ref]["sources"][0] == artifacts.citation_source(ref)
    assert bound[ref]["claim"]["numeric_authority"] == "not_applicable"
    assert artifacts._sources == before
    with pytest.raises(ValueError):
        answer_citations("An invented source [P01:S999].", artifacts, [])


def test_reader_and_calculator_share_newly_observed_source_lookup():
    from mcp import Client
    from mcp.server import MCPServer
    from sec_agent.agent_runtime.dell_case_artifacts import register_case_artifact_tools
    from test_research_session import _new_worker_fixture
    artifacts = DellCaseArtifacts([_new_worker_fixture()])
    source = {"result_state": "numeric_fact", "numeric_fact_authority": True,
        "numeric_fact_id": "NUMFACT::new-full-id", "ticker": "TEST", "value_decimal": "123", "unit": "USD",
        "period_start": "2025-01-01", "period_end": "2025-12-31"}
    def lookup(ref):
        return source if ref == source["numeric_fact_id"] else artifacts.source_item(ref)
    server = MCPServer("source-lookup-fixture")
    register_case_artifact_tools(server, artifacts, source_lookup=lookup)
    async def exercise():
        async with Client(server, raise_exceptions=False) as client:
            result = await client.call_tool("read_research_source", {"source_id": source["numeric_fact_id"]})
            assert not result.is_error and result.structured_content["value_decimal"] == "123"
            assert result.structured_content["period_end"] == "2025-12-31"
            rejected = await client.call_tool("read_research_source", {"source_id": "NUMFACT::new"})
            assert rejected.is_error and "unknown_source_id" in str(rejected.content)
    asyncio.run(exercise())
    with pytest.raises(ValueError, match="unknown_source_id"):
        artifacts.source_item(source["numeric_fact_id"])  # no cross-session mutation


def _calculate(expression="a / 2", operands=None):
    request = SourceBoundCalculation(expression=expression, operands=operands or {"a": {"source_id": "fact"}},
        result_unit="test_unit", rationale="Fixture arithmetic, not a financial conclusion.")
    return calculate_from_sources(request, _lookup)


def test_scoped_fts_search_returns_exact_reread_and_preserves_source_authority():
    from test_research_session import _new_worker_fixture
    artifacts = DellCaseArtifacts([_new_worker_fixture()])
    other = deepcopy(artifacts)
    passage = "前文 Unicode € " * 150 + "Goodwill impairment was 1,578; this is a test fixture." + " context" * 200
    source = {"result_state": "source_bound_passage", "title": "Fixture annual report",
              "passage": passage, "numeric_fact_authority": False}
    artifacts._sources["P01:S999"] = source
    original = deepcopy(artifacts._sources)
    result = artifacts.search_sources('"Goodwill impairment"')
    hit = result["matches"][0]
    assert hit["source_id"] == "P01:S999" and hit["numeric_fact_authority"] is False
    assert "Goodwill impairment" in hit["snippet"]
    window = artifacts.read_source(**hit["read_arguments"])
    assert window["text"] == passage[window["offset"]:window["offset"] + 2000]
    assert "Goodwill impairment was 1,578" in window["text"]
    assert artifacts._sources == original
    assert not other.search_sources('"Goodwill impairment"')["matches"]
    with pytest.raises(ValueError, match="query_invalid"):
        artifacts.search_sources('"unclosed')
    assert not artifacts.search_sources('"nonexistent; DROP TABLE sources;"')["matches"]


def test_source_search_is_available_through_native_mcp_and_case_adapter():
    from mcp import Client
    from mcp.server import MCPServer
    from sec_agent.agent_runtime.dell_case_artifacts import register_case_artifact_tools
    from sec_agent.agent_runtime.dell_case_review_agent import CASE_TOOLS
    from test_research_session import _new_worker_fixture
    assert "search_research_sources" in CASE_TOOLS
    server = MCPServer("scoped-search-test")
    artifacts = DellCaseArtifacts([_new_worker_fixture()])
    register_case_artifact_tools(server, artifacts)
    async def exercise():
        async with Client(server, raise_exceptions=False) as client:
            result = await client.call_tool("search_research_sources", {"query": "revenue"})
            assert not result.is_error
            assert "matches" in result.structured_content
            invalid = await client.call_tool("search_research_sources", {"query": '"unclosed'})
            assert invalid.is_error
    asyncio.run(exercise())


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




def test_calculator_reuses_saved_calculation_without_promoting_or_copying_parent_tree():
    parent = _calculate()
    original = deepcopy(parent)
    request = SourceBoundCalculation(expression="prior / 2", operands={"prior": {"source_id": parent["calculation_id"]}},
        result_unit="test_unit", rationale="Synthetic chained arithmetic; no financial conclusion.")
    child = calculate_from_sources(request, lambda _: parent)
    assert child["value_decimal"] == "25" and parent == original
    assert not child["numeric_fact_authority"] and not child["financial_semantics_verified"]
    binding = child["operands"]["prior"]
    assert binding["authority"] == "non_authoritative_calculation"
    assert binding["source_calculation"]["calculation_id"] == parent["calculation_id"]
    assert binding["source_calculation"]["expression"] == parent["expression"]
    assert "operands" not in binding["source_calculation"]  # parent ID links to the saved record, no growing tree copy
    forged = request.model_copy(update={"operands": {"prior": request.operands["prior"].model_copy(update={"literal": "999"})}})
    with pytest.raises(ValueError, match="differs_from_observed_calculation"):
        calculate_from_sources(forged, lambda _: parent)


@pytest.mark.parametrize("change", [
    {"arithmetic_verified": False}, {"numeric_fact_authority": True}, {"financial_semantics_verified": True},
    {"calculation_id": "CALC::another"}, {"value_decimal": "Infinity"},
])
def test_chained_calculator_rejects_invalid_saved_authority_identity_or_value(change):
    parent = _calculate()
    request = SourceBoundCalculation(expression="prior / 2", operands={"prior": {"source_id": parent["calculation_id"]}},
        result_unit="test_unit", rationale="Negative fixture only.")
    with pytest.raises(ValueError):
        calculate_from_sources(request, lambda _: {**parent, **change})


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
