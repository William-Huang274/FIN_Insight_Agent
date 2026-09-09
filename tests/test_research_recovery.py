"""Zero-provider native recovery: saved artifacts survive a new product run."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from mcp import Client

from sec_agent.agent_runtime.dell_specialist_agentic_graph import (
    DellSpecialistAgenticDependencies, DellSpecialistAgenticGraphError, build_dell_specialist_agentic_state_graph,
)
from sec_agent.agent_runtime.dell_case_review_agent import build_case_review_graph, build_case_reviewer, case_mcp_tools
from sec_agent.agent_runtime.research_session import build_research_session_graph
from test_dell_specialist_agentic_graph import _input, _ScriptedModel, _ToolPorts, _evidence_action, _finance_action, _submission
from test_dell_lead_research_graph import _graph, _task, _stop, _call, _seed, _worker_result, BRANCHES
from test_dell_case_review_agent import ScriptedNativeChat, review_fixture, call
from test_research_session import _phases, current_task_artifacts, FullSourceFixturePorts
from test_dell_research_mcp import _build_server


class RecoveryChat(ScriptedNativeChat):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        for message in messages:
            if isinstance(message, AIMessage) and message.additional_kwargs.get("reasoning_content"):
                assert message.additional_kwargs["reasoning_content"] == self.marker
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=self.replies.pop(0),
            additional_kwargs={"reasoning_content": self.marker}))])


def test_rejected_candidate_resumes_same_worker_without_retrieval_or_lifetime_reset():
    value = _input()
    value["max_model_turns"] = 3
    ports = _ToolPorts()
    first = _ScriptedModel([_evidence_action(), _finance_action(), _submission(evidence_id="UNKNOWN")])
    def graph(model, prior=None):
        return build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
            model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance), recovery_state=prior).compile()
    failed = graph(first).invoke(value)
    original = deepcopy(failed)
    assert failed["phase"] == "specialist_human_review_handoff_emitted"
    assert failed["last_submission_attempt"] and not failed["final_submission"]
    second = _ScriptedModel([_submission()])
    recovered = graph(second, failed).invoke({**value, "run_invocation_id": "explicit-second-run"})
    assert recovered["phase"] == "specialist_submission_accepted"
    assert recovered["task"] == failed["task"]
    assert recovered["notebook"]["model_turn_count"] == 4
    assert recovered["notebook"]["observations"] == failed["notebook"]["observations"]
    request = second.requests[0]
    assert request["execution_budget"]["remaining_model_turns"] == 3
    assert request["submission_to_repair"]["candidate"] == failed["last_submission_attempt"]["arguments"]
    assert failed == original
    with pytest.raises(DellSpecialistAgenticGraphError, match="recovery_task_or_data_scope_mismatch"):
        graph(second, failed).invoke({**value, "run_id": "another-thread"})


def test_product_can_resume_before_first_formal_paper_and_preserves_failed_attempt():
    async def exercise():
        phases, _, _ = _phases()
        value = {**_input(), "max_model_turns": 3}
        ports = FullSourceFixturePorts()
        calls = []
        async def research(request, config):
            calls.append(deepcopy(request))
            prior = request.get("failed_workpapers", [])
            model = _ScriptedModel([_submission()] if prior else [
                _evidence_action(), _finance_action(), _submission(evidence_id="UNKNOWN")])
            child = build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
                model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance),
                recovery_state=prior[-1]["agent_state"] if prior else None).compile()
            output = await child.ainvoke({**value, "run_invocation_id": str(len(calls))}, config)
            return {"phase": "research_needs_attention", "stop_reason": "offline_stop_before_financial_review",
                "tasks": [{"task_id": output["task"]["task_id"], "objective": request["question"]}],
                "task_results": [{"task_id": output["task"]["task_id"], "agent_state": output,
                    "status": "submitted" if output.get("final_submission") else "needs_attention"}]}
        phases["research"] = RunnableLambda(research)
        graph = build_research_session_graph(**phases).compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "no-paper-yet"}, "recursion_limit": 100}
        first = await graph.ainvoke({"question": "Recover original worker candidate without starting a replacement task."}, config)
        assert first["case_papers"] == []
        assert "continue_remaining" in first["__interrupt__"][0].value["actions"]
        final = await graph.ainvoke(Command(resume={"action": "continue_remaining"}), config)
        assert len(final["case_papers"]) == 1 and not final.get("report")
        assert final["case_papers"][0]["task"]["task_id"] == first["research_tasks"][0]["task_id"]
        assert calls[1]["unfinished_tasks"] == first["research_tasks"]
        assert final["research_failed_workpapers"] == first["research_failed_workpapers"]
        assert len(final["research_attempt_history"]) == 2
    asyncio.run(exercise())


def test_lead_restores_original_task_before_planning_and_can_supplement_submitted_branch():
    seed = _seed()
    original = _task("unfinished", BRANCHES[0], (seed["task"]["task_id"],))
    order = []
    def worker(task, dependencies, config):
        order.append(task["task_id"])
        assert dependencies[seed["task"]["task_id"]]["final_submission"] == seed["final_submission"]
        return _worker_result(task, seed)
    def lead(request):
        assert order == [original["task_id"]]
        return _stop(request, ready=True)
    graph, value = _graph(lead, worker, recovery_tasks=[original], require_all_branches=False)
    result = graph.invoke(value.model_dump(mode="json"))
    assert result["phase"] == "research_ready_for_review"
    assert [r["task_id"] for r in result["task_results"]] == [original["task_id"]]

    calls = []
    seed = _worker_result(_task("saved", BRANCHES[0]), seed)
    same_branch = _task("specific-gap", seed["task"]["branch_id"], (seed["task"]["task_id"],))
    def supplement(request):
        calls.append(request)
        return _call(request, "DelegateResearchTasksAction", tasks=[same_branch]) if len(calls) == 1 else _stop(request, ready=True)
    graph, value = _graph(supplement, worker, seed=seed, unfinished_only=True, require_all_branches=False)
    result = graph.invoke(value.model_dump(mode="json"))
    assert result["phase"] == "research_ready_for_review"
    assert result["task_results"][0]["task_id"] == same_branch["task_id"]


def test_product_interrupt_resumes_only_incomplete_reviewer_with_original_reads():
    async def exercise():
        phases, seen, _ = _phases()
        review_calls = 0
        original_review = None
        async def review(state, config):
            nonlocal review_calls, original_review
            review_calls += 1
            artifacts = current_task_artifacts(state)
            async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
                tools = await case_mcp_tools(client)
                reads = [call("read_research_artifact", {"paper_id": p["paper_id"]}, "read-" + p["paper_id"])
                         for p in artifacts.catalog()["papers"]]
                submit = [call("submit_case_review", {"review": review_fixture(artifacts)}, "submit")]
                models = {r: RecoveryChat(marker=r, replies=([reads] if r == "counter" else [reads, submit])
                          if review_calls == 1 else ([submit] if r == "counter" else [])) for r in ("counter", "verifier")}
                agents = {r: build_case_reviewer(role=r, model=models[r], tools=tools, artifacts=artifacts,
                          max_model_calls=1 if r == "counter" and review_calls == 1 else 3) for r in models}
                graph = build_case_review_graph(reviewers=agents, artifacts=artifacts, question=state["question"],
                    run_id="same-product-thread", run_invocation_id=str(review_calls),
                    previous_review=state.get("previous_review")).compile()
                result = await graph.ainvoke({"run_id": "same-product-thread", "run_invocation_id": str(review_calls)}, config)
                if review_calls == 1:
                    original_review = deepcopy(result)
                    assert result["counter"]["status"] == "incomplete_no_submission"
                    assert result["verifier"]["status"] == "review_submitted"
                else:
                    assert result["counter"]["status"] == "review_submitted"
                    assert result["counter"]["model_calls"] == 2
                    assert result["verifier"] == original_review["verifier"]
                    assert state["previous_review"]["counter"] == original_review["counter"]
                    assert not models["counter"].replies and not models["verifier"].replies
                    # Same-size content changes must invalidate the saved review,
                    # even if titles, IDs and catalog counts are unchanged.
                    changed = deepcopy(artifacts)
                    changed._papers["P01"]["workpaper"]["claims"][0]["statement"] += " changed"
                    with pytest.raises(ValueError, match="same_question_and_artifacts"):
                        build_case_review_graph(reviewers=agents, artifacts=changed, question=state["question"],
                            run_id="same-product-thread", run_invocation_id="changed", previous_review=original_review)
                return result
        phases["review"] = RunnableLambda(review)
        saver = InMemorySaver()
        config = {"configurable": {"thread_id": "review-recovery", "run_id": "one"}, "recursion_limit": 150}
        graph = build_research_session_graph(**phases).compile(checkpointer=saver)
        first = await graph.ainvoke({"question": "Continue only unfinished review checks without repeating research."}, config)
        assert "continue_remaining" in first["__interrupt__"][0].value["actions"]
        assert not first.get("report")
        # Rebuild the real parent against its native saver, as on a new server run.
        graph = build_research_session_graph(**phases).compile(checkpointer=saver)
        final = await graph.ainvoke(Command(resume={"action": "continue_remaining"}), config)
        assert final["phase"] == "ready_for_human_review"
        assert seen["research"] == 1 and review_calls == 2
        assert len(final["research_review_history"]) == 2
        assert final["research_review_history"][0]["result"] == original_review
    asyncio.run(exercise())
