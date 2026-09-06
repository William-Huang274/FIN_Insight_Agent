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
    report_citations, validated_revision,
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


class NativeFixtureModel(BaseChatModel):
    marker: str
    replies: list
    seen: list = []

    @property
    def _llm_type(self):
        return "zero-provider-convergence-fixture"

    def bind_tools(self, tools, **kwargs):
        self.seen.append([t.name for t in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        previous = [m for m in messages if isinstance(m, AIMessage)]
        assert all(m.additional_kwargs.get("reasoning_content") == self.marker for m in previous)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=self.replies[len(previous)],
            additional_kwargs={"reasoning_content": self.marker}))])


@pytest.mark.parametrize("material", [False, True])
def test_six_responsible_authors_then_writer_verifier_native_checkpoints(artifacts, material):
    async def run():
        original = artifacts.read_paper("P01")
        feedback = {p: [{"finding_id": "fixture"}] for p in PAPERS}
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            limits = {"model_calls": 12, "tool_calls": 32}
            agents = {}
            for pid in PAPERS:
                model = NativeFixtureModel(marker=pid, replies=[
                    [call("read_research_artifact", {"paper_id": pid}, "read")],
                    [call("submit_paper_revision", {"revision": revision_fixture(artifacts, pid)}, "submit")]])
                agents["author_"+pid] = build_case_output_agent(role="repair", model=model, tools=tools,
                    artifacts=artifacts, feedback=feedback[pid], paper_id=pid, limits=limits)
            ref = "P01:" + original["claims"][0]["claim_id"]
            prose = ("Synthetic report fixture checks source resolution only, not any financial conclusion. " * 4) + f"[{ref}]"
            report = {"title": "Synthetic convergence report", "narrative_markdown": prose}
            writer = NativeFixtureModel(marker="writer", replies=[
                [call("read_current_workpaper", {"paper_id": "P99"}, "bad")],
                [call("read_current_workpaper", {"paper_id": "P01"}, "read")],
                [call("submit_case_report", {"report": report}, "submit")]])
            agents["writer"] = build_case_output_agent(role="writer", model=writer, tools=tools, artifacts=artifacts, limits=limits)
            review = {"summary": "Synthetic final review checks graph sequencing and source contracts only, never economic truth.",
                "findings": ([{"finding_id": "F1", "severity": "material", "report_quote": "Synthetic report fixture",
                    "diagnosis": "Synthetic negative must remain visible as needs revision.",
                    "requested_change": "Synthetic finding only; do not claim actual financial review."}] if material else []),
                "unresolved_data_requests": []}
            model = NativeFixtureModel(marker="verifier", replies=[[call("submit_report_review", {"review": review}, "review")]])
            agents["verifier"] = build_case_output_agent(role="verifier", model=model, tools=tools, artifacts=artifacts, limits=limits)
            saver = InMemorySaver()
            graph = build_case_convergence_graph(agents=agents, artifacts=artifacts, question="fixture only", feedback=feedback,
                run_id="run", run_invocation_id="invoke").compile(checkpointer=saver)
            assert len(list(graph.get_subgraphs())) == 8
            state = await graph.ainvoke({"run_id": "run", "run_invocation_id": "invoke"},
                {"configurable": {"thread_id": "case"}, "recursion_limit": 100})
            assert len(state["revisions"]) == 6
            assert state["phase"] == ("case_report_needs_revision" if material else "case_report_ready_for_human_review")
            assert ref in state["report"]["citations"]
            assert "reasoning_content" not in json.dumps(state)
            assert artifacts.read_paper("P01") == original
            assert all("read_research_artifact" not in names for names in writer.seen)
            checkpoints = list(saver.list(None))
            for actor in agents:
                rows = [c for c in checkpoints if c.config["configurable"].get("checkpoint_ns", "").startswith(actor+":")]
                assert rows
                last = max(rows, key=lambda c: len(c.checkpoint["channel_values"].get("messages", [])))
                messages = last.checkpoint["channel_values"]["messages"]
                marker = actor.removeprefix("author_")
                assert all(m.additional_kwargs["reasoning_content"] == marker for m in messages if isinstance(m, AIMessage))
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


def test_actual_review_feedback_and_new_scope_are_bound_without_rewriting_old_authority():
    from pathlib import Path
    from scripts.qualification.dell_q1_specialist_paid_shadow.prepare_case_convergence import prepare
    from sec_agent.agent_runtime.dell_specialist_paid_shadow import (
        CaseConvergenceScope, load_dell_q1_paid_shadow_authority,
    )
    from sec_agent.agent_runtime.deepseek_structured_agents import load_deepseek_structured_agent_config
    old_path = Path("configs/research/evals/fin_ia_0_1_3_s3_dell_case_native_review_a1_authority_v1_0.json")
    old = load_dell_q1_paid_shadow_authority(old_path)
    assert old.decision_digest == "bfd1149f19d65d628f020640d3660a56515ad8db8483b421d2bc443ecc45225e"
    data = prepare()
    assert set(data["feedback"]) == set(PAPERS)
    assert data["host_assisted"] is True
    assert any(f["origin"].startswith("explicit_host") for f in data["feedback"]["P08"])
    config = load_deepseek_structured_agent_config("configs/research/fin_ia_0_1_3_dell_case_convergence_native_v1_0.json")
    scope = {"seed_state_host_path": "test", "seed_state_sha256": "a"*64, "repair_paper_ids": list(PAPERS),
        "node_budgets": {r: config.token_budget_basis["specialist"].model_dump(mode="json") for r in ("repair", "writer", "verifier")},
        "node_limits": {r: {"model_calls": 12, "tool_calls": 32} for r in ("repair", "writer", "verifier")}}
    CaseConvergenceScope.model_validate_json(json.dumps(scope))
    scope["repair_paper_ids"] = ["P99"]
    with pytest.raises(ValueError, match="roles_or_papers"):
        CaseConvergenceScope.model_validate_json(json.dumps(scope))
