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
