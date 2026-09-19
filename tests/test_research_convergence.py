"""Native responsibility routing with scripted models, not financial quality."""
import asyncio
from copy import deepcopy
import json

from langgraph.checkpoint.memory import InMemorySaver
from mcp import Client
import pytest

from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent, ReportReview
from sec_agent.agent_runtime.case_review_agent import case_mcp_tools
from sec_agent.agent_runtime.research_convergence import build_research_convergence_graph, route_material_findings, research_decision_context
from test_report_synthesis_agent import NativeFixtureModel, revision_fixture
from test_case_review_agent import call
from test_lead_research_graph import _task, _worker_result, BRANCHES
from test_research_mcp import _build_server
from test_research_session import _new_worker_fixture


def artifact_fixture():
    return CaseArtifacts([_worker_result(_task("first"), _new_worker_fixture()),
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


def test_decision_context_marks_changed_versions_without_inventing_semantic_resolution():
    artifacts = artifact_fixture()
    original = artifacts.read_paper('P02')
    base = research_decision_context(artifacts, artifacts, {}, question='Overall task', research_review_context={})
    revised = deepcopy(original)
    # A trusted-native artifact fixture changes claim metadata only. This does
    # not establish that its unchanged prose or financial conclusion is correct.
    revised['claims'][0]['authority_note'] = 'Revised fixture qualifier.'
    response = {'finding_id': 'verifier:F1', 'disposition': 'corrected', 'explanation': 'Author claims a local fix.'}
    revision = {'status': 'revision_submitted', 'workpaper': revised, 'finding_responses': [response]}
    current = artifacts.with_revisions({'P02': revision})
    reviews = {'verifier': {'unresolved_data_requests': ['Check the denominator.']},
               'incomplete_review_records': {'counter': {'status': 'review_incomplete', 'recorded_findings': []}}}
    state = {'synthesis': {'narrative_markdown': 'Previous judgment'}, 'revisions': {'P02': revision},
        'artifact_history': [{'actor': 'synthesis', 'decision_context': base}], 'correction_round': 1,
        'pending_feedback': {'P02': [{'finding_id': 'verifier:F1', 'diagnosis': 'Still needs independent checking.'}]}}
    decision = research_decision_context(artifacts, current, state, question='Overall task', research_review_context=reviews)
    changed = next(p for p in decision['papers'] if p['paper_id'] == 'P02')
    assert decision['previous_synthesis_status'] == 'requires_reassessment_against_current_papers'
    assert changed['baseline_status'] == 'superseded_version_not_a_financial_verdict'
    assert changed['changed_claim_ids'] == [original['claims'][0]['claim_id']]
    assert changed['changed_prose_fields'] == []
    assert changed['author_responses'] == [response] and changed['pending_findings']
    assert decision['review_unresolved_data_requests']['verifier'] == ['Check the denominator.']
    assert decision['incomplete_review_records'] == reviews['incomplete_review_records']
    assert current.read_paper(**changed['arguments']) == revised
    assert current.read_paper(**{'paper_id': 'P02', 'section': 'sources'}) == artifacts.read_paper('P02', 'sources')
    assert artifacts.read_paper('P02') == original
    unaffected = next(p for p in decision['papers'] if p['paper_id'] == 'P01')
    assert unaffected['baseline_status'] == 'current_version' and unaffected['changed_claim_ids'] == []
    assert original['narrative_markdown'] not in json.dumps(decision)  # Navigation, not duplicate full papers.
    decision['papers'][1]['author_responses'][0]['explanation'] = 'Changed request copy'
    assert state['revisions']['P02']['finding_responses'][0]['explanation'] == 'Author claims a local fix.'


def test_legacy_synthesis_without_version_basis_requires_reassessment():
    artifacts = artifact_fixture()
    view = research_decision_context(artifacts, artifacts, {'synthesis': {'title': 'Saved older synthesis'}},
        question='Current task', research_review_context={})
    assert view['previous_synthesis_status'] == 'requires_reassessment_against_current_papers'


async def exercise_case(*, terminal_owner=None, research_owner=None, repeat=False, initial_feedback=None, existing_state=None, local_writer_edits=False, depth=None, hierarchical=False, unchanged_repair=False, discovered_issue=False, authoring_stages=False, author_ready=True):
    artifacts = artifact_fixture()
    if depth == "focused":
        artifacts = CaseArtifacts([_worker_result(_task("first"), _new_worker_fixture())])
    sequence, contexts = [], {}
    async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
        tools = await case_mcp_tools(client)
        def make_agent(role, current, *, feedback, paper_id, correction_round, revising_report):
            sequence.append((role, paper_id, correction_round))
            ref = "P01:" + current.read_paper("P01")["claims"][0]["claim_id"]
            prose = "Deterministic cited research plumbing fixture. This is a synthetic test of native data handoff, not a Dell financial conclusion. " * 3 + f"[{ref}]"
            output_role = "decision" if role == "lead_decision" else "verifier" if role.endswith("verifier") else role
            if role == 'prepare':
                replies = [[call('submit_authoring_brief', {'brief': {
                    'answer':'Scoped research answer', 'argument_plan':['Evidence then conclusion'],
                    'decisions':['Retain scoped finding'], 'material_conditions':['Same period only'],
                    'unresolved':[] if author_ready else ['Material evidence unavailable'], 'ready':author_ready}}, 'prepare')]]
            elif role == "lead_decision":
                dispositions = [{"paper_id": pid, "finding_id": f["finding_id"], "disposition": "repair",
                    "rationale": "Synthetic targeted correction based on the supplied original finding, not financial approval.",
                    "requested_change": "Recheck only the affected fixture paper and associated prose.",
                    "expected_progress": "A source-bound correction or explicit unresolved response.", "citation_ids": []}
                    for pid, rows in (feedback or {}).items() for f in rows]
                replies = [[call("submit_lead_issue_decision", {"decision": {"summary": "Synthetic Lead disposition preserves unrelated research and original findings.",
                    "action": "repair" if dispositions else "synthesize", "dispositions": dispositions}}, "decide")]]
                if discovered_issue and correction_round == 0:
                    value = replies[0][0]["args"]["decision"]
                    value["action"] = "repair"
                    value["new_findings"] = [{"paper_id": "P02", "finding_id": "lead_new_scope", "disposition": "repair",
                        "rationale": "Exact fixture text requires a scoped clarification discovered by the Lead.",
                        "requested_change": "Clarify the scope in the fixture prose.", "expected_progress": "The affected prose states the limitation."}]
            elif role == "repair":
                revision = revision_fixture(current, paper_id)
                if not unchanged_repair:
                    revision["narrative_markdown"] += f"\n\nFixture amendment in correction round {correction_round}; not a financial quality assertion."
                revision["finding_responses"] = [{"finding_id": f["finding_id"], "disposition": "corrected",
                    "explanation": "A deterministic author amendment with real fixture sources, not semantic verification."} for f in feedback]
                replies = [[call("submit_paper_revision", {"revision": revision}, "revision")]]
            elif role.endswith("verifier"):
                owner = research_owner if role == "research_verifier" else terminal_owner
                findings = [finding(owner)] if owner and (repeat or correction_round == 0) else []
                replies = [[call("submit_report_review", {"review": {**independent_review(findings), "completion": "complete"}}, "verify")]]
            elif role == "writer" and revising_report and local_writer_edits:
                replies = [[call("submit_report_edits", {"edits": [
                    {"old_str": f"[{ref}]", "new_str": f"Locally revised wording [{ref}]"}]}, "local-edit")]]
            else:
                method = "lead" if role == "synthesis" else "writer"
                submission = "submit_research_synthesis" if role == "synthesis" else "submit_case_report"
                arg = "synthesis" if role == "synthesis" else "report"
                replies = [[call("get_research_method", {"method_id": method}, "method"),
                            call("read_current_workpaper", {"paper_id": "P02"}, "current")],
                           [call(submission, {arg: {"title": "Native research fixture", "narrative_markdown": prose}}, "submit")]]
            model = NativeFixtureModel(marker=f"{role}-private", replies=replies)
            contexts[(role, paper_id, correction_round)] = model
            if role == 'writer' and authoring_stages:
                output_role = 'lead_writer'
            return build_case_output_agent(role=output_role, model=model, tools=tools, artifacts=current,
                feedback=feedback, paper_id=paper_id, limits={"model_calls": 6, "tool_calls": 12},
                report_revision=role == "writer" and revising_report, require_responsibility=role.endswith("verifier"))
        saver = InMemorySaver()
        graph = build_research_convergence_graph(artifacts=artifacts, question="Synthetic question on growth quality and realization",
            hierarchical=hierarchical, authoring_stages=authoring_stages,
            feedback=initial_feedback or {}, research_review_context={"counter": independent_review(), "verifier": independent_review()},
            make_agent=make_agent, existing_state=existing_state, human_feedback="Explicit fixture revision request" if existing_state else None,
            execution_plan={"depth": depth, "rationale": "Synthetic scope-specific route qualification, not a model's financial judgment.",
                "omitted_steps_reason": "Omit repeated prose generation; preserve independent final source verification.",
                "escalation_conditions": "Material evidence findings return to the actual responsible research author."} if depth else None).compile(checkpointer=saver)
        config = {"configurable": {"thread_id": "native-research-convergence"}, "recursion_limit": 180}
        result = await graph.ainvoke({}, config)
        saved = await graph.aget_state(config)
        assert saved.values["artifact_history"] == result["artifact_history"]
        assert "-private" not in json.dumps(result)
        return result, sequence, contexts


def test_focused_workpaper_goes_directly_to_independent_final_verification():
    result, sequence, _ = asyncio.run(exercise_case(depth="focused"))
    assert [s[0] for s in sequence] == ["report_verifier"]
    assert result["report"]["citations"]
    assert result["phase"] == "case_report_ready_for_human_review"


def test_integrated_research_omits_duplicate_synthesis_and_keeps_final_review():
    result, sequence, models = asyncio.run(exercise_case(depth="integrated"))
    assert [s[0] for s in sequence] == ["writer", "report_verifier"]
    writer_input = json.loads(models[("writer", None, 0)].contexts[0][1].content)
    assert writer_input["research_review"]["counter"]
    verifier_input = json.loads(models[("report_verifier", None, 0)].contexts[0][1].content)
    assert verifier_input["completed_research_reviews"]["verifier"]
    assert result["phase"] == "case_report_ready_for_human_review"


def test_integrated_material_findings_repair_actual_owner_without_duplicate_synthesis():
    result, sequence, _ = asyncio.run(exercise_case(depth="integrated", terminal_owner="research"))
    assert [s[0] for s in sequence] == ["writer", "report_verifier", "repair", "writer", "report_verifier"]
    assert set(result["revisions"]) == {"P02"}


def test_lead_actual_method_read_and_revised_papers_enter_writer_without_private_histories():
    feedback = {"P02": [{"finding_id": "counter:F1", "severity": "material", "paper_id": "P02",
        "diagnosis": "Synthetic initial cross-paper review finding", "requested_change": "Check the actual source."}]}
    result, sequence, models = asyncio.run(exercise_case(initial_feedback=feedback))
    assert [s[0] for s in sequence] == ["repair", "synthesis", "research_verifier", "writer", "report_verifier"]
    assert result["phase"] == "case_report_ready_for_human_review"
    lead = models[("synthesis", None, 0)]
    decision = json.loads(lead.contexts[0][1].content)['research_decision_context']
    assert decision['question'] == 'Synthetic question on growth quality and realization'
    affected = next(p for p in decision['papers'] if p['paper_id'] == 'P02')
    assert affected['pending_findings'] == feedback['P02']
    assert affected['author_responses'][0]['disposition'] == 'corrected'
    assert 'not independent closure' in affected['response_status_notice']
    saved_lead = next(r for r in result['artifact_history'] if r['actor'] == 'synthesis')
    assert saved_lead['decision_context'] == decision
    writer = json.loads(models[('writer', None, 0)].contexts[0][1].content)
    assert writer['research_decision_context']['previous_synthesis_status'] == 'current_paper_versions_not_automatic_approval'
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


def test_native_parent_writer_revision_uses_edits_not_full_report_or_research_rerun():
    result, sequence, models = asyncio.run(exercise_case(terminal_owner="writer", local_writer_edits=True))
    review_input = json.loads(models[("report_verifier", None, 1)].contexts[0][1].content)
    assert "Locally revised wording" in review_input["report_changes_from_previous_review"]
    assert "correction review" in review_input["instruction"]
    assert [s[0] for s in sequence] == ["synthesis", "research_verifier", "writer", "report_verifier", "writer", "report_verifier"]
    reports = [r["output"] for r in result["artifact_history"] if r["actor"] == "writer"]
    edit = reports[1]["applied_edits"][0]
    assert reports[1]["narrative_markdown"] == reports[0]["narrative_markdown"].replace(edit["old_str"], edit["new_str"], 1)
    assert reports[1]["citations"] == reports[0]["citations"]
    writer = models[("writer", None, 1)]
    assert len(writer.contexts) == 1 and "submit_report_edits" in writer.seen[0]
    assert result["phase"] == "case_report_ready_for_human_review"


def test_research_finding_returns_only_responsible_paper_then_lead_and_both_reviews():
    result, sequence, models = asyncio.run(exercise_case(terminal_owner="research"))
    assert [s[0] for s in sequence] == ["synthesis", "research_verifier", "writer", "report_verifier",
        "repair", "synthesis", "research_verifier", "writer", "report_verifier"]
    assert set(result["revisions"]) == {"P02"} and result["phase"] == "case_report_ready_for_human_review"
    assert ("repair", "P01", 1) not in models
    seed = json.loads(models[("repair", "P02", 1)].contexts[0][1].content)
    assert seed["original_workpaper"] == artifact_fixture().read_paper("P02")
    assert "sources" not in seed
    assert "read_current_source" in seed["source_access"]
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


def test_followup_local_edit_hands_previous_review_and_real_diff_to_verifier():
    previous, _, _ = asyncio.run(exercise_case(depth="integrated"))
    original = deepcopy(previous)
    result, sequence, models = asyncio.run(exercise_case(depth="integrated", existing_state=previous, local_writer_edits=True))
    assert [row[0] for row in sequence] == ["writer", "report_verifier"]
    body = json.loads(models[("report_verifier", None, 0)].contexts[0][1].content)
    assert body["previous_review"] == original["report_review"]
    assert "Locally revised wording" in body["report_changes_from_previous_review"]
    assert previous == original and result["phase"] == "case_report_ready_for_human_review"


def test_native_verifier_receives_invalid_owner_feedback_then_corrects_without_weakening_schema():
    async def run():
        artifacts = artifact_fixture()
        malformed = independent_review([finding("research", pid="P99")])
        corrected = independent_review([finding("research")])
        model = NativeFixtureModel(marker="verifier-private", replies=[
            [call("submit_report_review", {"review": {**malformed, "completion": "complete"}}, "bad")],
            [call("submit_report_review", {"review": {**corrected, "completion": "complete"}}, "good")]])
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
