"""Native parent/child integration, not paid research or semantic gold."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from threading import Barrier, Lock

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from mcp import Client
import pytest

from sec_agent.agent_runtime.research_session import build_research_session_graph, current_task_artifacts
from sec_agent.agent_runtime.research_convergence import build_research_convergence_graph
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent, CaseOutputState
from sec_agent.agent_runtime.dell_case_review_agent import build_case_review_graph, build_case_reviewer, case_mcp_tools
from sec_agent.agent_runtime.dell_lead_research_graph import build_dell_lead_research_graph
from sec_agent.agent_runtime.dell_specialist_agentic_graph import SpecialistAgenticInput
from test_dell_case_convergence_agent import NativeFixtureModel, revision_fixture
from test_dell_case_review_agent import call, review_fixture
from test_dell_lead_research_graph import _task, _call, _stop, _worker_result, BRANCHES, CATALOG
from test_dell_research_mcp import _build_server
from test_dell_specialist_agentic_graph import _input, _run, _ScriptedModel, _ToolPorts, _evidence_action, _finance_action, _submission


class FullSourceFixturePorts(_ToolPorts):
    def _observation(self, request, **kwargs):
        rows = deepcopy(kwargs["content"])
        for row in rows:
            if "ref_id" in row:
                row.update(result_state="reviewed_evidence", evidence_id=row["ref_id"], writer_citable=True,
                           numeric_fact_authority=False, source_url="https://example.com/fixture")
            if "fact_id" in row:
                row.update(result_state="numeric_fact", numeric_fact_authority=True, ticker="DELL")
        return super()._observation(request, **{**kwargs, "content": rows})


def _new_worker_fixture():
    return _run(_ScriptedModel([_evidence_action(), _finance_action(), _submission()]), FullSourceFixturePorts())


def _phases(*, material=False, incomplete=False, fail_convergence=False, full_profile=False, fail_one_first=False, fail_synthesis_once=False):
    seen = {"research": 0, "review": 0, "converge": 0, "ask": 0}
    models = {}
    synthesis_failed = False
    root = Path(__file__).resolve().parents[1]
    case = json.loads((root / "configs/research/cases/dell_growth_quality.json").read_text(encoding="utf-8"))
    profile = json.loads((root / "configs/research/runtime/research_session.json").read_text(encoding="utf-8"))
    catalog = case["branch_topics"] if full_profile else CATALOG
    branches = tuple(b["branch_id"] for b in catalog)

    async def research(request, config):
        seen["research"] += 1
        turns = []
        barrier, lock = Barrier(2, timeout=15), Lock()
        running = 0
        max_running = 0
        delegated = [_task("price", branches[0]), _task("compute", branches[1])]
        seeds = {paper["task"]["task_id"]: paper for paper in request.get("completed_workpapers", [])}
        if seeds:
            assert fail_one_first and set(seeds) == {"task:price"}
            delegated = [delegated[1]]
        if full_profile:
            delegated += [_task(f"theme{i}", branch, ("task:price",) if i == 2 else ()) for i, branch in enumerate(branches[2:], 2)]
        def lead(payload):
            turns.append(payload)
            assert payload["research_question"] == request["question"]
            if len(turns) == 1:
                assert len(payload["workpapers"]) == len(seeds)
                return _call(payload, "DelegateResearchTasksAction", tasks=delegated)
            if full_profile and len(turns) == 2:
                assert {row["task_id"] for row in payload["workpapers"]} == {"task:price", "task:compute"}
                return _call(payload, "DelegateResearchTasksAction", tasks=[_task("followup", branches[-1], ("task:price", "task:compute"))])
            if full_profile and len(payload["workpapers"]) < 10:
                return _call(payload, "ContinueResearchTasksAction")
            return _stop(payload, ready=not incomplete and not (fail_one_first and seen["research"] == 1))
        def worker(task, dependencies, cfg):
            nonlocal running, max_running
            assert set(dependencies) == set(task["dependency_ids"])
            with lock:
                running += 1
                max_running = max(max_running, running)
            try:
                if full_profile and task["task_id"] in {"task:price", "task:compute"}:
                    barrier.wait()
                result = _worker_result(task, _new_worker_fixture())
                if fail_one_first and seen["research"] == 1 and task["task_id"] == "task:compute":
                    result.update(phase="specialist_human_review_handoff_emitted", final_submission=None,
                                  human_review_handoff={"reason": "synthetic_single_transport_failure"})
                return result
            finally:
                with lock:
                    running -= 1
        graph = build_dell_lead_research_graph(expected_input=SpecialistAgenticInput.model_validate_json(json.dumps(_input())),
            research_question=request["question"], branch_catalog=catalog, allowed_branch_ids=branches, seed_workpapers=seeds,
            unfinished_only=bool(seeds),
            max_tasks=profile["max_tasks"], max_parallel_tasks=profile["max_parallel_tasks"],
            max_lead_turns=profile["nodes"]["lead"]["limits"]["model_calls"], model_turn=lead, run_child=worker).compile()
        result = await graph.ainvoke(_input(), config)
        if full_profile:
            assert max_running == 2 and len(turns) >= 6 and len(result["task_results"]) == 10
        return result

    async def review(state, config):
        seen["review"] += 1
        artifacts = current_task_artifacts(state)
        assert len(artifacts.catalog()["papers"]) == (10 if full_profile else 2)
        assert "messages" not in state and "reasoning_content" not in json.dumps(state)
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            reviewers = {}
            for role in ("counter", "verifier"):
                result = review_fixture(artifacts)
                if material:
                    result["findings"] = [{"finding_id": "F1", "paper_id": "P01", "severity": "material",
                        "problematic_quote": artifacts.read_paper("P01")["thesis"],
                        "diagnosis": "Synthetic fixture requires a specific author response, not a quality finding.",
                        "requested_change": "Reply to this deterministic fixture with source-backed agreement or disagreement."}]
                models[role] = NativeFixtureModel(marker=role+"-private", replies=[
                    [call("read_research_artifact", {"paper_id": p["paper_id"]}, "read-"+p["paper_id"])
                     for p in artifacts.catalog()["papers"]],
                    [call("submit_case_review", {"review": result}, "review-submit")]])
                reviewers[role] = build_case_reviewer(role=role, model=models[role], tools=tools, artifacts=artifacts)
            graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question=state["question"],
                run_id="parent-fixture", run_invocation_id="review-fixture").compile()
            return await graph.ainvoke({"run_id": "parent-fixture", "run_invocation_id": "review-fixture"}, config)

    async def converge(state, config, existing=None):
        seen["converge"] += 1
        if fail_convergence:
            raise ValueError("synthetic_convergence_failure_no_report")
        artifacts = current_task_artifacts(state)
        feedback = state["feedback"]
        assert set(feedback) == ({"P01"} if material and not existing else set())
        if material and not existing:
            assert {row["finding_id"] for row in feedback["P01"]} == {"counter:F1", "verifier:F1"}
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            limits = {"model_calls": 8, "tool_calls": 24}
            ref = "P01:" + artifacts.read_paper("P01")["claims"][0]["claim_id"]
            report = {"title": "Native parent integration fixture", "narrative_markdown":
                "This is a deterministic plumbing fixture, not a Dell financial conclusion. " * 5 + f"[{ref}]"}
            review_result = {"summary": "This independent scripted report review tests parent handoff only and cannot establish research quality.",
                            "findings": [], "unresolved_data_requests": []}
            def make_agent(role, current, *, feedback, paper_id, correction_round, revising_report):
                nonlocal synthesis_failed
                key = "terminal" if role == "report_verifier" else role
                if role == "repair":
                    if fail_synthesis_once:
                        seen["repair"] = seen.get("repair", 0) + 1
                    revision = revision_fixture(current, paper_id)
                    revision["finding_responses"] = [{"finding_id": f["finding_id"], "disposition": "disagreed_with_sources",
                        "explanation": "Synthetic local plumbing test, not an actual financial correction."} for f in feedback]
                    reply = call("submit_paper_revision", {"revision": revision}, "rev")
                elif role.endswith("verifier"):
                    reply = call("submit_report_review", {"review": review_result}, "check")
                elif role == "synthesis":
                    if fail_synthesis_once and not synthesis_failed:
                        synthesis_failed = True
                        # Simulate the old native model loop ending without a
                        # structured output, including its completed checkpoint.
                        return create_agent(model=NativeFixtureModel(marker="synthesis-private", replies=[[]]),
                            tools=[], state_schema=CaseOutputState, name="case_synthesis_report")
                    reply = call("submit_research_synthesis", {"synthesis": report}, "synthesis")
                else:
                    reply = call("submit_case_report", {"report": report}, "report")
                models[key] = NativeFixtureModel(marker=key+"-private", replies=[[], [reply]] if fail_synthesis_once and role == "synthesis" else [[reply]])
                return build_case_output_agent(role="verifier" if role.endswith("verifier") else role,
                    model=models[key], tools=tools, artifacts=current, limits=limits, feedback=feedback, paper_id=paper_id,
                    require_responsibility=role.endswith("verifier"), report_revision=role == "writer" and revising_report)
            graph = build_research_convergence_graph(artifacts=artifacts, question=state["question"], feedback=feedback,
                make_agent=make_agent, research_review_context=state["case_review"], existing_state=existing,
                human_feedback=existing.get("message") if existing else None).compile()
            return await graph.ainvoke({}, config)

    async def revise_research(state, config):
        return await converge({**state, "feedback": {}}, config, existing=state)

    async def ask(state, config):
        seen["ask"] += 1
        artifacts = current_task_artifacts(state)
        ref = "P01:" + artifacts.read_paper("P01")["claims"][0]["claim_id"]
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            model = NativeFixtureModel(marker="ask-private", replies=[[call("submit_case_answer",
                {"answer_markdown": f"Fixture answer tied to the current task's paper [{ref}]."}, "ask")]])
            agent = build_case_output_agent(role="writer", model=model, tools=tools, artifacts=artifacts,
                limits={"model_calls": 3, "tool_calls": 6}, allow_answers=True, answer_only=True)
            return await agent.ainvoke({key: value for key, value in state.items() if key != "case_papers"}, config)

    return {"research": RunnableLambda(research), "review": RunnableLambda(review), "converge": RunnableLambda(converge),
            "revise_research": RunnableLambda(revise_research),
            "writer": RunnableLambda(ask), "quick_writer": RunnableLambda(ask), "verifier": RunnableLambda(ask)}, seen, models


@pytest.mark.parametrize("material,full_profile", [(False, False), (True, False), (True, True)])
def test_new_question_native_parent_to_report_human_point_and_followup_without_research_rerun(material, full_profile):
    async def exercise():
        phases, seen, models = _phases(material=material, full_profile=full_profile)
        saver = InMemorySaver()
        graph = build_research_session_graph(**phases).compile(checkpointer=saver)
        config = {"configurable": {"thread_id": "fresh-parent-fixture"}, "recursion_limit": 160}
        question = "Fixture: evaluate growth quality, earnings realization and future execution pressure."
        result = await graph.ainvoke({"question": question}, config)
        assert result["phase"] == "ready_for_human_review" and result["__interrupt__"]
        assert len(result["case_papers"]) == len(result["research_tasks"]) == (10 if full_profile else 2)
        assert "messages" not in json.dumps(result["case_papers"])
        assert "-private" not in json.dumps({k: v for k, v in result.items() if k != "__interrupt__"})
        assert set(result["revisions"]) == ({"P01"} if material else set())
        assert "independent_research_review" in str(models["synthesis"].contexts[0])
        assert "research_synthesis" in str(models["writer"].contexts[0])
        assert "citations" not in json.loads(models["terminal"].contexts[0][1].content)["report"]
        original = deepcopy(result["report"])
        # Recompile to simulate a fresh graph factory over the same native store.
        graph = build_research_session_graph(**phases).compile(checkpointer=saver)
        result = await graph.ainvoke(Command(resume={"action": "ask", "message": "Explain the fixture source", "answer_mode": "quick"}), config)
        assert result["report"] == original and result["__interrupt__"]
        assert seen == {"research": 1, "review": 1, "converge": 1, "ask": 1}
        assert result["conversation"][-1]["citations"]
        if full_profile:
            result = await graph.ainvoke(Command(resume={"action": "revise", "message": "Please clarify the actual research judgment."}), config)
            assert seen["research"] == seen["review"] == 1 and seen["converge"] == 2
            assert result["__interrupt__"] and result["phase"] == "ready_for_human_review"
            assert "Please clarify the actual research judgment." in str(models["writer"].contexts[0])
        result = await graph.ainvoke(Command(resume={"action": "accept"}), config)
        assert result["phase"] == "human_reviewed_not_released" and not result.get("__interrupt__")
        namespaces = {c.config["configurable"].get("checkpoint_ns", "") for c in saver.list(None)}
        assert any("case_review:" in name and "counter:" in name for name in namespaces)
        assert any("convergence:" in name and "writer:" in name for name in namespaces)
    asyncio.run(exercise())


def test_incomplete_research_keeps_submitted_work_and_does_not_write_a_report():
    async def exercise():
        phases, seen, _ = _phases(incomplete=True)
        graph = build_research_session_graph(**phases).compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "incomplete-parent"}, "recursion_limit": 120}
        result = await graph.ainvoke({"question": "This is a deliberately incomplete research fixture."}, config)
        assert result["phase"] == "research_needs_attention" and len(result["case_papers"]) == 2
        assert not result.get("report") and seen["review"] == seen["converge"] == 0
        with pytest.raises(ValueError, match="cannot_be_accepted"):
            await graph.ainvoke(Command(resume={"action": "accept"}), config)
    asyncio.run(exercise())


def test_failure_keeps_earlier_stage_artifacts_in_native_checkpoint_without_fake_report():
    async def exercise():
        phases, seen, _ = _phases(fail_convergence=True)
        graph = build_research_session_graph(**phases).compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "failed-parent"}, "recursion_limit": 120}
        with pytest.raises(ValueError, match="synthetic_convergence_failure"):
            await graph.ainvoke({"question": "Test preserved work when a later node fails."}, config)
        saved = await graph.aget_state(config)
        assert len(saved.values["case_papers"]) == 2 and saved.values["case_review"]["counter"]["status"] == "review_submitted"
        assert not saved.values.get("report") and seen["converge"] == 1
    asyncio.run(exercise())


def test_native_retry_after_synthesis_failure_does_not_repeat_completed_author_or_research():
    async def exercise():
        phases, seen, _ = _phases(material=True, fail_synthesis_once=True)
        saver = InMemorySaver()
        config = {"configurable": {"thread_id": "native-synthesis-retry"}, "recursion_limit": 160}
        graph = build_research_session_graph(**phases).compile(checkpointer=saver)
        with pytest.raises(ExceptionGroup) as failed:
            await graph.ainvoke({"question": "Keep accepted author corrections when a later synthesis fails."}, config)
        assert "research_actor_ended_without_submission:synthesis" in repr(failed.value)
        assert seen["repair"] == seen["research"] == seen["review"] == 1
        graph = build_research_session_graph(**phases).compile(checkpointer=saver)
        result = await graph.ainvoke(None, config)
        assert result["phase"] == "ready_for_human_review" and result["__interrupt__"]
        assert seen["repair"] == seen["research"] == seen["review"] == 1
        assert set(result["revisions"]) == {"P01"}
    asyncio.run(exercise())


@pytest.mark.parametrize("fail_remaining_once", [False, True])
def test_explicit_native_continuation_only_runs_missing_theme_preserves_original_failure(fail_remaining_once):
    async def exercise():
        phases, seen, _ = _phases(fail_one_first=True)
        saver = InMemorySaver()
        graph = build_research_session_graph(**phases).compile(checkpointer=saver)
        config = {"configurable": {"thread_id": "continue-missing", "run_id": "first"}, "recursion_limit": 120}
        original = await graph.ainvoke({"question": "Complete the case without rerunning a submitted specialist."}, config)
        assert original["phase"] == "research_needs_attention" and len(original["case_papers"]) == 1
        assert "continue_remaining" in original["__interrupt__"][0].value["actions"]
        first_paper = deepcopy(original["case_papers"][0])
        graph = build_research_session_graph(**phases).compile(checkpointer=saver)
        next_config = {**config, "configurable": {**config["configurable"], "run_id": "second"}}
        if fail_remaining_once:
            async def failed_remaining(request):
                assert request["completed_workpapers"] == [first_paper]
                raise ValueError("synthetic_known_continuation_failure")
            broken = build_research_session_graph(**{**phases, "research": RunnableLambda(failed_remaining)}).compile(checkpointer=saver)
            with pytest.raises(ValueError, match="synthetic_known_continuation_failure"):
                await broken.ainvoke(Command(resume={"action": "continue_remaining"}), next_config)
            saved = await graph.aget_state(next_config)
            assert saved.tasks[0].name == "remaining_research" and saved.values["case_papers"] == [first_paper]
            next_config["configurable"]["run_id"] = "third"
            continued = await graph.ainvoke(None, next_config)  # native retry of the known failed node, no manual state update
        else:
            continued = await graph.ainvoke(Command(resume={"action": "continue_remaining"}), next_config)
        assert continued["case_papers"][0] == first_paper and len(continued["case_papers"]) == 2
        assert continued["report"] and continued["phase"] == "ready_for_human_review"
        history = continued["research_attempt_history"]
        assert history[0]["outcomes"] == original["research_outcomes"]
        assert history[0]["outcomes"][1]["status"] == "needs_attention"
        assert history[1]["outcomes"] == [{"task_id": "task:compute", "status": "submitted"}]
        assert len(continued["research_tasks"]) == 2 and seen == {"research": 2, "review": 1, "converge": 1, "ask": 0}
        assert len([snap for snap in saver.list(None) if snap.config["configurable"].get("checkpoint_ns") == ""]) > 2
    asyncio.run(exercise())
