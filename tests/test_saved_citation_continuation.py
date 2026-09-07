"""Citation continuation through native artifacts; no paid/model quality claim."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
import pytest

from sec_agent.agent_runtime.dell_case_convergence_agent import (
    answer_citations, answer_reference_ids, build_case_output_agent, observed_sources, saved_citation_bindings,
)
from scripts.qualification.context_continuation_comparison import Probe
from test_dell_case_review_agent import artifacts


CALC = "CALC::saved-margin"
FACT = "NUMFACT::saved-revenue"


class PaginatedReadProbe(Probe):
    def _generate(self, *args, **kwargs):
        result = super()._generate(*args, **kwargs)
        for call in result.generations[0].message.tool_calls:
            if call["name"] == "read_current_source":
                call["args"].update(offset=7, max_characters=100)
        return result


def citation():
    return {"claim": {"kind": "calculation", "statement": "gp / revenue * 100 = 20 percent",
        "numeric_authority": "non_authoritative", "authority_note": "Synthetic persisted calculation, not issuer disclosure."},
        "sources": [{"source_id": CALC, "value_decimal": "20", "unit": "percent",
            "numeric_fact_authority": False, "text": "Saved citation summary without executable operands."},
            {"source_id": FACT, "result_state": "numeric_fact", "numeric_fact_authority": True,
             "ticker": "DELL", "metric_id": "Revenue", "value_decimal": "100", "unit": "USD",
             "period_start": "2025-02-01", "period_end": "2026-01-30", "fiscal_period": "FY",
             "citation_urls": ["https://example.com/fixture"], "source_observation_ids": ["observation-fixture"]}]}


def legacy_read(record=None, **window_changes):
    text = json.dumps(record or citation())
    window = {"citation_id": CALC, "text": text, "offset": 0, "next_offset": None, "total_characters": len(text)}
    window.update(window_changes)
    return ToolMessage(content=json.dumps(window), name="read_current_source", tool_call_id="legacy")


def test_complete_legacy_binding_and_embedded_fact_retain_identity_without_recalculation(artifacts):
    rows = [legacy_read()]
    original = deepcopy(rows)
    result = answer_citations(f"Historical calculation [{CALC}] with input [{FACT}].", artifacts, rows)
    assert result[CALC] == citation()
    assert result[FACT]["sources"] == [citation()["sources"][1]]
    assert observed_sources(rows) == {}  # No executable CALC or newly admitted S2 fact.
    assert rows == original
    with pytest.raises(ValueError, match="answer_source_ids_not_observed"):
        answer_citations(f"Unobserved [{CALC}-invented].", artifacts, rows)


@pytest.mark.parametrize("invalid", ["partial", "suffix", "bad_json", "wrong_id", "wrong_shape", "error", "other_tool", "model", "user"])
def test_partial_or_non_host_content_cannot_create_citations(artifacts, invalid):
    row = legacy_read()
    if invalid == "partial":
        row = legacy_read(next_offset=5000, total_characters=5000)
    elif invalid == "suffix":
        row = legacy_read(offset=1)
    elif invalid == "bad_json":
        row = legacy_read(text="not a citation", total_characters=14)
    elif invalid == "wrong_id":
        row = legacy_read(citation_id="CALC::different-record")
    elif invalid == "wrong_shape":
        row = legacy_read({"claim": "model claim", "sources": []})
    elif invalid == "error":
        row = row.model_copy(update={"status": "error"})
    elif invalid == "other_tool":
        row = row.model_copy(update={"name": "arbitrary_search"})
    elif invalid == "model":
        row = AIMessage(content=row.content)
    elif invalid == "user":
        row = HumanMessage(content=row.content)
    assert saved_citation_bindings([row]) == {}
    with pytest.raises(ValueError, match="answer_source_ids_not_observed"):
        answer_citations(f"Do not admit [{CALC}].", artifacts, [row])


def test_conflicting_canonical_binding_is_not_silently_replaced():
    changed = citation()
    changed["sources"][0]["value_decimal"] = "999"
    with pytest.raises(ValueError, match="saved_citation_binding_conflict"):
        saved_citation_bindings([legacy_read(), legacy_read(changed)])


@pytest.fixture
def citation_only_artifacts():
    def missing(_):
        raise ValueError("No case source: only the supplied native observation is available")
    return SimpleNamespace(source_item=missing)


def test_bare_saved_calculation_is_bound_and_unknown_bare_id_cannot_bypass_validation(citation_only_artifacts):
    artifacts = citation_only_artifacts
    prose = f"Saved calculation {CALC} 回读：result 20 percent; operand [{FACT}]."
    bound = answer_citations(prose, artifacts, [legacy_read()])
    assert list(bound) == [CALC, FACT]
    assert bound[CALC] == citation()
    with pytest.raises(ValueError, match="answer_source_ids_not_observed"):
        answer_citations(f"{CALC}-invented = 20; real operand [{FACT}].", artifacts, [legacy_read()])
    with pytest.raises(ValueError, match="answer_source_ids_not_observed"):
        answer_citations(f"{CALC}/invented = 20; real operand [{FACT}].", artifacts, [legacy_read()])


def test_markdown_literals_urls_and_links_do_not_create_citations(citation_only_artifacts):
    artifacts = citation_only_artifacts
    prose = (f"`[{CALC}]`\n\n```text\n{CALC}\n```\n\n"
             f"[documentation {CALC}](https://example.com) https://example.com/{CALC}\n\n"
             f"Actual input [{FACT}].")
    assert answer_reference_ids(prose) == [FACT]
    assert list(answer_citations(prose, artifacts, [legacy_read()])) == [FACT]


def test_bare_paper_and_calculation_ids_preserve_order_and_sentence_punctuation():
    assert answer_reference_ids("P02:C1 supports CALC::saved-margin. Input [NUMFACT::saved-revenue].") == [
        "P02:C1", CALC, FACT]
    # Legacy bracket syntax remains exact: never bind a prefix of an unknown ID.
    assert answer_reference_ids("[CALC::saved-margin/suffix]") == [CALC + "/suffix"]
    assert answer_reference_ids("P02:C1/C4/C13") == ["P02:C1/C4/C13"]


@pytest.mark.parametrize("recorded", [False, True])
@pytest.mark.parametrize("bracketed", [False, True])
def test_native_read_pagination_checkpoint_and_submission_share_the_full_binding(artifacts, recorded, bracketed):
    async def run():
        record = citation()
        if recorded:
            record["sources"][0]["calculation"] = {
                "arithmetic_verified": True, "financial_semantics_verified": False}
        # Current server citation -> paginated content + full native artifact.
        calc_reference = f"[{CALC}]" if bracketed else CALC
        answer = f"Historical result {calc_reference} and operand [{FACT}]."
        model = PaginatedReadProbe(report={"read_ids": [CALC, FACT], "answer": answer})
        agent = build_case_output_agent(role="writer", model=model, tools=[], artifacts=artifacts,
            limits={"model_calls": 2, "tool_calls": 3}, allow_answers=True, answer_only=True)
        agent.checkpointer = InMemorySaver()
        config = {"configurable": {"thread_id": "citation-continuation"}}
        result = await agent.ainvoke({"request_action": "ask", "messages": [legacy_read(record),
            HumanMessage(content="Continue using the saved citations.")]}, config)
        assert set(result["output"]["citations"]) == {CALC, FACT}
        assert result["output"]["answer_markdown"] == answer
        assert len(model.contexts) == 2  # Original submission accepted, no repair call.
        saved = await agent.aget_state(config)
        reads = [m for m in saved.values["messages"] if isinstance(m, ToolMessage) and m.artifact]
        calc_read = next(m for m in reads if CALC in m.artifact["citations"])
        body = json.loads(calc_read.content)
        assert body["citation_status"] == "bound"
        assert len(body["text"]) == 100 and body["offset"] == 7 and body["next_offset"] == 107
        assert body["verification_status"] == {
            "arithmetic_verified": "verified" if recorded else "not_recorded",
            "financial_semantics_verified": "not_verified" if recorded else "not_recorded"}
        # Tool-content eviction/summary must not remove the citation artifact.
        evicted = calc_read.model_copy(update={"content": "Old read omitted from model context."})
        bound = answer_citations(f"Still bound [{CALC}] [{FACT}].", artifacts, [evicted])
        assert bound[CALC] == record and observed_sources([evicted]) == {}
    asyncio.run(run())
