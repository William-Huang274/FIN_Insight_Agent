"""Native responsibility routing with scripted models, not financial quality."""
import asyncio
from copy import deepcopy
import json

from langgraph.checkpoint.memory import InMemorySaver
from mcp import Client
import pytest

from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent, ReportReview
from sec_agent.agent_runtime.dell_case_review_agent import case_mcp_tools
from sec_agent.agent_runtime.research_convergence import build_research_convergence_graph, route_material_findings
from test_dell_case_convergence_agent import NativeFixtureModel, revision_fixture
from test_dell_case_review_agent import call
from test_dell_lead_research_graph import _task, _worker_result, BRANCHES
from test_dell_research_mcp import _build_server
from test_research_session import _new_worker_fixture


def artifact_fixture():
    return DellCaseArtifacts([_worker_result(_task("first"), _new_worker_fixture()),
                              _worker_result(_task("second", BRANCHES[1]), _new_worker_fixture())])


def finding(owner, *, pid="P02", finding_id="F1", severity="material"):
    return {"finding_id": finding_id, "severity": severity,
        "report_quote": "Deterministic cited research plumbing fixture",
        "diagnosis": "Synthetic finding used only to verify responsibility routing and not a financial judgment.",
        "requested_change": "Recheck the responsible claim against actual fixture sources without accepting the reviewer as truth.",
        "responsibility": owner, "paper_ids": [pid] if owner == "research" else []}


def independent_review(findings=()):
    return {"summary": "Independent scripted review for graph qualification; it does not prove live financial quality or public acceptance.",
            "findings": list(findings), "unresolved_data_requests": []}


async def exercise_case(*, terminal_owner=None, research_owner=None, repeat=False, initial_feedback=None, existing_state=None):
    artifacts = artifact_fixture()
    sequence, contexts = [], {}
    async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
        tools = await case_mcp_tools(client)
        def make_agent(role, current, *, feedback, paper_id, correction_round, revising_report):
            sequence.append((role, paper_id, correction_round))
            ref = "P01:" + current.read_paper("P01")["claims"][0]["claim_id"]
            prose = "Deterministic cited research plumbing fixture. This is a synthetic test of native data handoff, not a Dell financial conclusion. " * 3 + f"[{ref}]"
            output_role = "verifier" if role.endswith("verifier") else role
            if role == "repair":
                revision = revision_fixture(current, paper_id)
                revision["finding_responses"] = [{"finding_id": f["finding_id"], "disposition": "corrected",
                    "explanation": "A deterministic author amendment with real fixture sources, not semantic verification."} for f in feedback]
                replies = [[call("submit_paper_revision", {"revision": revision}, "revision")]]
            elif role.endswith("verifier"):
                owner = research_owner if role == "research_verifier" else terminal_owner
                findings = [finding(owner)] if owner and (repeat or correction_round == 0) else []
                replies = [[call("submit_report_review", {"review": independent_review(findings)}, "verify")]]
            else:
                method = "lead" if role == "synthesis" else "writer"
                submission = "submit_research_synthesis" if role == "synthesis" else "submit_case_report"
                arg = "synthesis" if role == "synthesis" else "report"
                replies = [[call("get_research_method", {"method_id": method}, "method"),
                            call("read_current_workpaper", {"paper_id": "P02"}, "current")],
                           [call(submission, {arg: {"title": "Native research fixture", "narrative_markdown": prose}}, "submit")]]
            model = NativeFixtureModel(marker=f"{role}-private", replies=replies)
            contexts[(role, paper_id, correction_round)] = model
            return build_case_output_agent(role=output_role, model=model, tools=tools, artifacts=current,
                feedback=feedback, paper_id=paper_id, limits={"model_calls": 6, "tool_calls": 12},
                report_revision=role == "writer" and revising_report, require_responsibility=role.endswith("verifier"))
        saver = InMemorySaver()
        graph = build_research_convergence_graph(artifacts=artifacts, question="Synthetic question on growth quality and realization",
            feedback=initial_feedback or {}, research_review_context={"counter": independent_review(), "verifier": independent_review()},
            make_agent=make_agent, existing_state=existing_state, human_feedback="Explicit fixture revision request" if existing_state else None).compile(checkpointer=saver)
        config = {"configurable": {"thread_id": "native-research-convergence"}, "recursion_limit": 180}
        result = await graph.ainvoke({}, config)
        saved = await graph.aget_state(config)
        assert saved.values["artifact_history"] == result["artifact_history"]
        assert "-private" not in json.dumps(result)
        return result, sequence, contexts


def test_lead_actual_method_read_and_revised_papers_enter_writer_without_private_histories():
    feedback = {"P02": [{"finding_id": "counter:F1", "severity": "material", "paper_id": "P02",
        "diagnosis": "Synthetic initial cross-paper review finding", "requested_change": "Check the actual source."}]}
    result, sequence, models = asyncio.run(exercise_case(initial_feedback=feedback))
    assert [s[0] for s in sequence] == ["repair", "synthesis", "research_verifier", "writer", "report_verifier"]
    assert result["phase"] == "case_report_ready_for_human_review"
    lead = models[("synthesis", None, 0)]
    assert any(getattr(m, "name", "") == "get_research_method" for m in lead.contexts[-1])
    assert result["revisions"]["P02"]["workpaper"]["thesis"] in str(lead.contexts[0])
    writer_input = json.loads(models[("writer", None, 0)].contexts[0][1].content)
    assert writer_input["research_synthesis"]["narrative_markdown"] == result["synthesis"]["narrative_markdown"]
    assert "citations" not in writer_input["research_synthesis"]
    assert "lead-private" not in json.dumps(writer_input)


def test_writer_only_feedback_does_not_rerun_authors_lead_or_research_review():
    result, sequence, _ = asyncio.run(exercise_case(terminal_owner="writer"))
    assert [s[0] for s in sequence] == ["synthesis", "research_verifier", "writer", "report_verifier", "writer", "report_verifier"]
    assert result["phase"] == "case_report_ready_for_human_review" and result["correction_round"] == 1
    assert len([r for r in result["artifact_history"] if r["actor"] == "writer"]) == 2


def test_research_finding_returns_only_responsible_paper_then_lead_and_both_reviews():
    result, sequence, models = asyncio.run(exercise_case(terminal_owner="research"))
    assert [s[0] for s in sequence] == ["synthesis", "research_verifier", "writer", "report_verifier",
        "repair", "synthesis", "research_verifier", "writer", "report_verifier"]
    assert set(result["revisions"]) == {"P02"} and result["phase"] == "case_report_ready_for_human_review"
    assert ("repair", "P01", 1) not in models
    assert result["revisions"]["P02"]["workpaper"]["thesis"] in str(models[("synthesis", None, 1)].contexts[0])


def test_research_review_repairs_before_first_report_not_a_premature_writer():
    result, sequence, _ = asyncio.run(exercise_case(research_owner="research"))
    assert [s[0] for s in sequence] == ["synthesis", "research_verifier", "repair", "synthesis", "research_verifier", "writer", "report_verifier"]
    assert result["phase"] == "case_report_ready_for_human_review"


@pytest.mark.parametrize("owner", ["data_tool", "human"])
def test_host_or_human_block_keeps_report_and_does_not_order_cosmetic_repair(owner):
    result, sequence, _ = asyncio.run(exercise_case(terminal_owner=owner))
    assert len(sequence) == 4 and result["phase"] == "case_report_needs_revision"
    assert result["report_review"]["findings"][0]["responsibility"] == owner and not result.get("revisions")


def test_repeated_material_failure_stops_after_one_correction_and_preserves_both_findings():
    result, sequence, _ = asyncio.run(exercise_case(terminal_owner="writer", repeat=True))
    assert len(sequence) == 6 and result["phase"] == "case_report_needs_revision"
    assert result["stop_reason"] == "material_findings_remain_after_targeted_correction"
    assert len([r for r in result["artifact_history"] if r["actor"] == "report_verifier"]) == 2


def test_prewrite_data_failure_has_no_report_and_preserves_synthesis():
    result, sequence, _ = asyncio.run(exercise_case(research_owner="data_tool"))
    assert len(sequence) == 2 and "report" not in result
    assert result["phase"] == "research_convergence_needs_attention" and result["synthesis"]


def test_explicit_followup_revision_uses_saved_research_and_routes_prior_research_finding():
    previous, _, _ = asyncio.run(exercise_case())
    previous["report_review"] = independent_review([finding("research")])
    original = deepcopy(previous)
    result, sequence, models = asyncio.run(exercise_case(existing_state=previous))
    assert [s[0] for s in sequence] == ["repair", "synthesis", "research_verifier", "writer", "report_verifier"]
    assert previous == original and result["phase"] == "case_report_ready_for_human_review"
    assert "Explicit fixture revision request" in str(models[("repair", "P02", 1)].contexts[0])


def test_native_verifier_receives_invalid_owner_feedback_then_corrects_without_weakening_schema():
    async def run():
        artifacts = artifact_fixture()
        malformed = independent_review([finding("research", pid="P99")])
        corrected = independent_review([finding("research")])
        model = NativeFixtureModel(marker="verifier-private", replies=[
            [call("submit_report_review", {"review": malformed}, "bad")],
            [call("submit_report_review", {"review": corrected}, "good")]])
        agent = build_case_output_agent(role="verifier", model=model, tools=[], artifacts=artifacts,
            limits={"model_calls": 3, "tool_calls": 4}, require_responsibility=True)
        from langchain_core.messages import HumanMessage, ToolMessage
        result = await agent.ainvoke({"messages": [HumanMessage(content="Verify this fixture")],
            "report": {"title": "Fixture review", "narrative_markdown": "Deterministic cited research plumbing fixture"}})
        assert result["output"]["findings"][0]["paper_ids"] == ["P02"]
        assert any(isinstance(m, ToolMessage) and m.status == "error" and "unknown_or_duplicate_responsible_paper" in m.content for m in result["messages"])
    asyncio.run(run())


@pytest.mark.parametrize("mutation", ["missing_owner", "unknown_paper", "no_paper", "writer_papers", "duplicate_finding"])
def test_invalid_responsibility_is_not_silently_routed_to_writer(mutation):
    review = independent_review([finding("research")])
    item = review["findings"][0]
    if mutation == "missing_owner": item["responsibility"] = None
    elif mutation == "unknown_paper": item["paper_ids"] = ["P99"]
    elif mutation == "no_paper": item["paper_ids"] = []
    elif mutation == "writer_papers": item["responsibility"] = "writer"
    else: review["findings"].append(deepcopy(item))
    with pytest.raises(ValueError, match="invalid_review_responsibility"):
        route_material_findings(review, artifact_fixture(), stage="report_review", round_index=0)
