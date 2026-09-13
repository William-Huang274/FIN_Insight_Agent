"""Native loop / MCP / citation qualification, not a semantic gold evaluation."""
import asyncio
import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from mcp import Client
import pytest

from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.agent_runtime.case_review_agent import (
    CaseReview, build_case_reviewer, build_case_review_graph, case_mcp_tools, validate_case_review,
)
from test_research_mcp import _build_server


@pytest.fixture
def artifacts():
    """Build source-bound synthetic papers without a saved research bundle."""
    from test_lead_research_graph import _task, _worker_result
    from test_research_session import _new_worker_fixture

    seed = _new_worker_fixture()
    return CaseArtifacts([_worker_result(_task(f"synthetic-{i}"), seed) for i in range(8)])


def review_fixture(artifacts):
    return {"summary": "Synthetic review used to verify tool access and state transitions.",
        "assessments": [{"paper_id": p["paper_id"], "assessment": "Synthetic source access only; no financial verdict."}
                        for p in artifacts.catalog()["papers"]], "findings": [],
        "unresolved_data_requests": [], "withdrawn_finding_reasons": {}}


@pytest.mark.parametrize("kind", ["case", "revision", "report"])
def test_all_review_submission_boundaries_reject_observed_omitted_unfinished_work(kind):
    from sec_agent.agent_runtime.case_review_agent import SubmittedCaseReview, RevisionCaseReview
    from sec_agent.agent_runtime.report_synthesis_agent import SubmittedReportReview, ReportReview
    pending = "The necessary attribution source has not been inspected, so this assessment remains incomplete."
    legacy = {"summary": pending}
    if kind != "report":
        legacy["assessments"] = [{"paper_id": "P01", "assessment": pending}]
    schema = {"case": SubmittedCaseReview, "revision": RevisionCaseReview, "report": SubmittedReportReview}[kind]
    # Historical records remain readable. New submissions cannot repeat the
    # observed omission that silently defaulted an unfinished review to [].
    (ReportReview if kind == "report" else CaseReview).model_validate(legacy)
    with pytest.raises(ValueError):
        schema.model_validate(legacy)
    with pytest.raises(ValueError):
        schema.model_validate({**legacy, "completion": "complete", "unresolved_data_requests": [pending]})
    parsed = schema.model_validate({**legacy, "completion": "incomplete", "unresolved_data_requests": [pending]})
    assert parsed.unresolved_data_requests == [pending]


class ScriptedNativeChat(BaseChatModel):
    replies: list
    marker: str

    @property
    def _llm_type(self):
        return "zero-provider-native-loop-fixture"

    def bind_tools(self, tools, **kwargs):
        names = {t.name for t in tools}
        assert ({"read_research_artifact", "calculate_research_metric", "submit_case_review"}.issubset(names)
                or {"read_review_target", "submit_case_review"}.issubset(names)
                or names == {"record_case_finding", "submit_case_review"})
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        for message in messages:
            if isinstance(message, AIMessage):
                assert message.additional_kwargs["reasoning_content"] == self.marker
        index = sum(isinstance(m, AIMessage) for m in messages)
        reply = self.replies[index]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=reply,
            additional_kwargs={"reasoning_content": self.marker}))])


def call(name, args, identity):
    return {"name": name, "args": args, "id": identity, "type": "tool_call"}


def test_revision_review_scope_preserves_valid_findings_and_never_passes_whole_case():
    from copy import deepcopy
    from test_research_convergence import artifact_fixture
    from sec_agent.agent_runtime.case_artifacts import revision_review_target

    async def exercise():
        base = artifact_fixture()
        original = base.read_paper("P01")
        revised = deepcopy(original)
        revised["claims"][0]["statement"] += " Revised synthetic statement."
        revision = {"status": "revision_submitted", "workpaper": revised, "finding_responses": [], "sources": {}}
        target = revision_review_target(base, "P01", revision)
        current = base.with_revisions({"P01": revision})
        cid = revised["claims"][0]["claim_id"]
        assert target["changed_claim_ids"] == [cid]
        assert base.read_paper("P01") == original
        valid = {"finding_id": "valid", "paper_id": "P01", "claim_ids": [cid], "severity": "advisory",
            "problematic_quote": revised["claims"][0]["statement"], "diagnosis": "Synthetic source-independent scope plumbing test.",
            "requested_change": "Inspect only this synthetic revision; this is not a financial result."}
        outside = {**valid, "finding_id": "outside", "claim_ids": ["UNCHANGED_OTHER_TOPIC"]}
        wrong_quote = {**valid, "finding_id": "wrong-quote", "problematic_quote": "Joined ... text that is not an exact quote."}
        final = {"summary": "Only the selected revision was checked in this synthetic test.",
            "assessments": [{"paper_id": "P01", "assessment": "Changed claim inspected; unchanged claims are not verified."}]}
        replies = [[call("read_review_target", {}, "read")],
            [call("record_case_finding", {"finding": valid}, "valid"),
             call("record_case_finding", {"finding": json.dumps(valid)}, "string"),
             call("record_case_finding", {"finding": outside}, "outside"),
             call("record_case_finding", {"finding": wrong_quote}, "badquote")],
            [call("submit_case_review", {"review": {**final, "completion": "complete", "unresolved_data_requests": []}}, "submit")]]
        agent = build_case_reviewer(role="verifier", model=ScriptedNativeChat(marker="local", replies=replies),
            tools=[], artifacts=current, revision_target=target, max_model_calls=3)
        tool_names = set(agent.get_graph().nodes["tools"].data.tools_by_name)
        assert "read_review_target" in tool_names
        assert not {"read_research_artifact", "research_artifact_catalog", "read_source_document"} & tool_names
        result = await agent.ainvoke({"messages": [HumanMessage(content="Review this revision only.")]})
        assert list(result["recorded_findings"]) == ["valid"]
        assert result["review"]["review_scope"]["kind"] == "revision_only"
        assert [f["finding_id"] for f in result["review"]["findings"]] == ["valid"]
        errors = [m.content for m in result["messages"] if isinstance(m, ToolMessage) and m.status == "error"]
        assert len(errors) == 3 and any("finding_outside_revision_scope" in e for e in errors)
        assert any("problematic_quote_not_exact" in e for e in errors)
        with pytest.raises(ValueError, match="read_missing_papers"):
            validate_case_review(CaseReview.model_validate(final), current, result["messages"], paper_ids=["P01"])
        # Full-case parent must not promote this narrower submission.
        from langchain_core.runnables import RunnableLambda
        reviewers = {r: RunnableLambda(lambda _: result) for r in ("counter", "verifier")}
        parent = build_case_review_graph(reviewers=reviewers, artifacts=current, question="Full case",
            run_id="scope", run_invocation_id="a1").compile()
        outcome = await parent.ainvoke({"run_id": "scope", "run_invocation_id": "a1"})
        assert outcome["phase"] == "case_review_incomplete"
        invalid_target = {**target, "current_digest": "stale"}
        with pytest.raises(ValueError, match="does_not_match"):
            build_case_reviewer(role="verifier", model=ScriptedNativeChat(marker="local", replies=[]),
                tools=[], artifacts=current, revision_target=invalid_target)
    asyncio.run(exercise())


def test_revision_submission_requires_explicit_completion_and_preserves_incomplete_work():
    from copy import deepcopy
    from test_research_convergence import artifact_fixture
    from sec_agent.agent_runtime.case_artifacts import revision_review_target

    async def exercise():
        base = artifact_fixture()
        revised = deepcopy(base.read_paper("P01"))
        revised["claims"][0]["statement"] += " Synthetic revision."
        revision = {"status": "revision_submitted", "workpaper": revised, "finding_responses": [], "sources": {}}
        target = revision_review_target(base, "P01", revision)
        pending = "A necessary attribution source has not yet been inspected."
        # Observed provider failure: prose admits unfinished work but omits the
        # structured list. Do not infer or fabricate that list from prose.
        omitted = {"summary": pending, "assessments": [{"paper_id": "P01", "assessment": pending}]}
        mismatch = {**omitted, "completion": "complete", "unresolved_data_requests": [pending]}
        explicit = {**omitted, "completion": "incomplete", "unresolved_data_requests": [pending]}
        replies = [[call("read_review_target", {}, "read")],
            [call("submit_case_review", {"review": omitted}, "omitted")],
            [call("submit_case_review", {"review": mismatch}, "mismatch")],
            [call("submit_case_review", {"review": explicit}, "explicit")]]
        agent = build_case_reviewer(role="verifier", model=ScriptedNativeChat(marker="local", replies=replies),
            tools=[], artifacts=base.with_revisions({"P01": revision}), revision_target=target, max_model_calls=4)
        result = await agent.ainvoke({"messages": [HumanMessage(content="Synthetic revision qualification.")]})
        responses = {m.tool_call_id: m for m in result["messages"] if isinstance(m, ToolMessage)}
        assert responses["omitted"].status == "error"
        assert "completion" in responses["omitted"].content and "unresolved_data_requests" in responses["omitted"].content
        assert responses["mismatch"].status == "error"
        assert "revision_completion_must_match" in responses["mismatch"].content
        assert responses["explicit"].status == "success"
        assert result["review"]["completion"] == "incomplete"
        assert result["review"]["unresolved_data_requests"] == [pending]
        assert result["review"]["summary"] == pending
    asyncio.run(exercise())


def test_budget_hint_keeps_provider_history_intact():
    from langchain.agents.middleware.types import ModelRequest
    from langchain_core.messages import SystemMessage
    from sec_agent.agent_runtime.case_review_agent import ReviewWorkBudget
    model = ScriptedNativeChat(marker="private", replies=[])
    history = [AIMessage(content="public", additional_kwargs={"reasoning_content": "private"}),
        ToolMessage(name="read_research_artifact", content="paper", tool_call_id="r",
            artifact={"section": "workpaper", "paper_id": "P01"})]
    request = ModelRequest(model=model, messages=history, system_message=SystemMessage(content="Issuer comes from user."),
        state={"messages": history, "thread_model_call_count": 22, "recorded_findings": {"F1": {}}})
    projected = ReviewWorkBudget(24).request_with_budget(request)
    assert "2 model call(s) remain" in projected.system_message.content
    assert "penultimate call retains tools" in projected.system_message.content
    assert projected.messages == history
    assert history[0].additional_kwargs["reasoning_content"] == "private"
    request.state["thread_model_call_count"] = 2
    assert ReviewWorkBudget(24).request_with_budget(request) is request  # Stable cache prefix, not a counter rewritten every turn.
    request.state.update(thread_model_call_count=40, run_model_call_count=2)
    assert ReviewWorkBudget(24).request_with_budget(request) is request  # Match the native run limit after an authorized resume.


def test_closeout_reserve_blocks_new_reads_without_fabricating_a_result():
    from types import SimpleNamespace
    from sec_agent.agent_runtime.case_review_agent import ReviewWorkBudget
    state = {"thread_model_call_count": 6, "messages": [ToolMessage(name="read_research_artifact", content="paper",
        tool_call_id="read", artifact={"paper_id": "P01", "section": "workpaper"})]}
    request = SimpleNamespace(state=state, tool_call={"name": "read_research_source", "id": "late-read"})
    result = ReviewWorkBudget(6).wrap_tool_call(request, lambda _: pytest.fail("late read must not execute"))
    assert result.status == "error" and "not executed" in result.content
    request.tool_call = {"name": "submit_case_review", "id": "close"}
    assert ReviewWorkBudget(6).wrap_tool_call(request, lambda _: "submitted") == "submitted"


def test_penultimate_review_can_correct_calculation_before_final_submission():
    from types import SimpleNamespace
    from langchain.agents.middleware.types import ModelRequest
    from sec_agent.agent_runtime.case_review_agent import ReviewWorkBudget
    from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources
    history = [ToolMessage(name="read_review_target", content="scope", tool_call_id="scope",
        artifact={"kind": "revision_only"})]
    tools = [SimpleNamespace(name=n) for n in ("calculate_research_metric", "read_research_source", "submit_case_review", "record_case_finding")]
    request = ModelRequest(model=ScriptedNativeChat(marker="fixture", replies=[]), messages=history, tools=tools,
        state={"messages": history, "run_model_call_count": 4})
    budget = ReviewWorkBudget(6)
    assert budget.request_with_budget(request).tools == tools
    # The fifth response has already incremented the native counter when its
    # tool executes. Previously this correction was rejected with one turn left.
    source = {"result_state": "numeric_fact", "numeric_fact_authority": True, "value_decimal": "-7"}
    calc = SourceBoundCalculation(expression="base - loss", operands={
        "base": {"literal": "11", "assumption_note": "Synthetic baseline"}, "loss": {"source_id": "NUMFACT::fixture"}},
        result_unit="USD", rationale="Synthetic decline from positive income to a signed loss.")
    tool_request = SimpleNamespace(state={**request.state, "run_model_call_count": 5},
        tool_call={"name": "calculate_research_metric", "id": "correction"})
    result = budget.wrap_tool_call(tool_request, lambda _: calculate_from_sources(calc, lambda _: source))
    assert result["value_decimal"] == "18"
    request.state["run_model_call_count"] = 5
    assert {t.name for t in budget.request_with_budget(request).tools} == {"submit_case_review", "record_case_finding"}
    tool_request.state["run_model_call_count"] = 6
    assert budget.wrap_tool_call(tool_request, lambda _: pytest.fail("final call cannot start another calculation")).status == "error"


def test_case_schema_factory_is_read_only_and_discovers_both_subgraphs(monkeypatch):
    from types import SimpleNamespace
    import sec_agent.agent_runtime.agent_server_entry as entry
    monkeypatch.setenv("FINSIGHT_DELL_SERVING_MODE", "case_workpaper_review_v1")
    monkeypatch.setattr(entry, "open_case_review_composition", lambda **kwargs: pytest.fail("schema read opened case/model/data"))

    async def exercise():
        async with entry.research_graph({}, SimpleNamespace(execution_runtime=None)) as graph:
            assert {name for name, _ in graph.get_subgraphs()} == {"counter", "verifier"}
            assert "counter" in graph.get_output_jsonschema()["properties"]
    asyncio.run(exercise())




def test_native_parallel_agents_errors_and_checkpointed_private_messages(artifacts):
    async def exercise():
        server = _build_server(case_artifacts=artifacts)
        async with Client(server, raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            source_id = next(s for s, item in artifacts.read_paper("P01", "sources").items() if item["result_state"] == "numeric_fact")
            read_calls = [call("read_research_artifact", {"paper_id": p["paper_id"]}, f"read{i}")
                          for i, p in enumerate(artifacts.catalog()["papers"])]
            good = review_fixture(artifacts)
            bad = {**good, "findings": [{"finding_id": "F1", "paper_id": "P01", "severity": "material",
                "problematic_quote": "THIS IS NOT IN THE ACTUAL PAPER", "diagnosis": "Synthetic exact quote negative.",
                "requested_change": "Correct the synthetic quote only."}]}
            replies = [read_calls, [call("read_research_source", {"source_id": "unknown"}, "badsource")],
                [call("calculate_research_metric", {"request": {"expression": "a / 2", "operands": {"a": {"source_id": source_id}},
                    "result_unit": "fixture", "rationale": "Test arithmetic only, not economic interpretation."}}, "calc")],
                [call("submit_case_review", {"review": {**bad, "completion": "complete"}}, "badreview")],
                [call("submit_case_review", {"review": {**good, "completion": "complete"}}, "goodreview")]]
            reviewers = {r: build_case_reviewer(role=r, model=ScriptedNativeChat(replies=replies, marker=r),
                tools=tools, artifacts=artifacts) for r in ("counter", "verifier")}
            saver = InMemorySaver()
            graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question="Synthetic native qualification",
                run_id="run-test", run_invocation_id="invoke-test").compile(checkpointer=saver)
            assert {name for name, _ in graph.get_subgraphs()} == {"counter", "verifier"}
            result = await graph.ainvoke({"run_id": "run-test", "run_invocation_id": "invoke-test"},
                {"configurable": {"thread_id": "fixture-thread"}, "recursion_limit": 150})
            assert result["phase"] == "case_review_ready_for_convergence"
            assert result["counter"]["model_calls"] == result["verifier"]["model_calls"] == 5
            assert "messages" not in result and "reasoning_content" not in json.dumps(result)
            checkpoints = list(saver.list(None))
            for role in ("counter", "verifier"):
                own = [c for c in checkpoints if c.config["configurable"].get("checkpoint_ns", "").startswith(role + ":")]
                assert own
                messages = max(own, key=lambda c: len(c.checkpoint["channel_values"].get("messages", []))).checkpoint["channel_values"]["messages"]
                ai = [m for m in messages if isinstance(m, AIMessage)]
                assert len(ai) == 5 and all(m.additional_kwargs["reasoning_content"] == role for m in ai)
                rejected = [m for m in messages if isinstance(m, ToolMessage) and m.status == "error"]
                assert len(rejected) == 2
                assert any("problematic_quote_not_exact" in m.content for m in rejected)
                assert all(isinstance(m.artifact, dict) for m in messages if isinstance(m, ToolMessage) and m.name == "read_research_artifact")
    asyncio.run(exercise())


def test_cannot_claim_all_papers_read_without_observation(artifacts):
    with pytest.raises(ValueError, match="read_missing_papers"):
        validate_case_review(CaseReview.model_validate(review_fixture(artifacts)), artifacts, [])


@pytest.mark.parametrize("withdraw", [False, True])
@pytest.mark.parametrize("malformed_sibling", [False, True])
def test_saved_finding_survives_limit_and_is_merged_without_rewriting(artifacts, withdraw, malformed_sibling):
    async def exercise():
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            finding = {"finding_id": "F-saved", "paper_id": "P01", "severity": "advisory",
                "problematic_quote": artifacts.read_paper("P01")["thesis"],
                "diagnosis": "Synthetic checkpoint test, not a financial diagnosis.",
                "requested_change": "Retain this finding across model calls and the parent graph."}
            reads = [call("read_research_artifact", {"paper_id": p["paper_id"]}, f"r{i}")
                for i, p in enumerate(artifacts.catalog()["papers"])]
            save = [call("record_case_finding", {"finding": finding}, "save")]
            if malformed_sibling:
                # Actual provider failure shape: JSON string instead of object.
                # Native validation rejects it without aborting the valid sibling.
                save.append(call("record_case_finding", {"finding": json.dumps(finding)}, "bad-sibling"))
            final = review_fixture(artifacts)
            if withdraw:
                final["withdrawn_finding_reasons"] = {"F-saved": "Subsequent source inspection disproved this synthetic finding."}
            reviewers = {role: build_case_reviewer(role=role, artifacts=artifacts, tools=tools,
                max_model_calls=2 if role == "counter" else 3,
                model=ScriptedNativeChat(marker=role, replies=[reads, save,
                    [call("submit_case_review", {"review": {**final, "completion": "complete"}}, "submit")]]))
                for role in ("counter", "verifier")}
            graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question="Fixture question",
                research_handoff={"synthesis_notes": "Unverified model coverage, not source truth."},
                run_id="saved", run_invocation_id="a1").compile(checkpointer=InMemorySaver())
            result = await graph.ainvoke({"run_id": "saved", "run_invocation_id": "a1"},
                {"configurable": {"thread_id": "saved-finding"}, "recursion_limit": 80})
            assert result["phase"] == "case_review_incomplete"
            assert result["counter"]["recorded_findings"]["F-saved"]["diagnosis"] == finding["diagnosis"]
            assert [f["finding_id"] for f in result["verifier"]["review"]["findings"]] == ([] if withdraw else ["F-saved"])
            # Recovery history is server-private and belongs only to its role.
            # Public projections and convergence must never receive that history.
            from apps.workbench.backend.api.v1.report_sessions import public_state
            projected = public_state({"values": {"phase": "research_needs_attention", "case_review": result}})
            assert "reasoning_content" not in json.dumps(projected)
            assert "recovery_state" not in json.dumps(projected)
    asyncio.run(exercise())


def test_targeted_claim_read_is_smaller_but_not_complete_review_coverage(artifacts):
    async def exercise():
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            reader = next(t for t in tools if t.name == "read_research_artifact")
            claim_id = artifacts.read_paper("P01", "claims")[0]["claim_id"]
            reply = await reader.ainvoke(call("read_research_artifact",
                {"paper_id": "P01", "section": "claims", "claim_ids": [claim_id]}, "target"))
            assert [c["claim_id"] for c in reply.artifact["content"]] == [claim_id]
            with pytest.raises(ValueError, match="read_missing_papers"):
                validate_case_review(CaseReview.model_validate(review_fixture(artifacts)), artifacts, [reply])
            assert len(json.dumps(reply.artifact["content"])) < len(json.dumps(artifacts.read_paper("P01")))
            source_reader = next(t for t in tools if t.name == "read_research_source")
            assert source_reader.args["max_characters"]["default"] == 4000
    asyncio.run(exercise())


def test_submitted_review_with_unchecked_work_does_not_enter_report_pipeline(artifacts):
    from langchain_core.runnables import RunnableLambda
    good = review_fixture(artifacts)
    incomplete = {**good, "unresolved_data_requests": ["The prior-period expense basis has not been inspected."]}
    reviewers = {r: RunnableLambda(lambda _, result=(incomplete if r == "counter" else good):
        {"review": result, "messages": []}) for r in ("counter", "verifier")}
    graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question="Fixture",
        run_id="pending", run_invocation_id="a1").compile()
    result = graph.invoke({"run_id": "pending", "run_invocation_id": "a1"})
    assert result["phase"] == "case_review_incomplete"
    assert result["counter"]["status"] == "incomplete_review"
    assert result["counter"]["review"]["unresolved_data_requests"]


def test_native_limit_keeps_peer_review_and_incomplete_checkpoint(artifacts):
    async def exercise():
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            reads = [call("read_research_artifact", {"paper_id": p["paper_id"]}, f"read{i}")
                     for i, p in enumerate(artifacts.catalog()["papers"])]
            reviewers = {
                "counter": build_case_reviewer(role="counter", model=ScriptedNativeChat(replies=[reads], marker="counter"),
                    tools=tools, artifacts=artifacts, max_model_calls=1),
                "verifier": build_case_reviewer(role="verifier", model=ScriptedNativeChat(
                    replies=[reads, [call("submit_case_review", {"review": {**review_fixture(artifacts), "completion": "complete"}}, "submit")]], marker="verifier"),
                    tools=tools, artifacts=artifacts, max_model_calls=2),
            }
            graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question="Bounded peer isolation qualification",
                run_id="limit-run", run_invocation_id="limit-attempt").compile(checkpointer=InMemorySaver())
            config = {"configurable": {"thread_id": "limited-review"}, "recursion_limit": 40}
            result = await graph.ainvoke({"run_id": "limit-run", "run_invocation_id": "limit-attempt"}, config)
            assert result["phase"] == "case_review_incomplete"
            assert result["counter"]["status"] == "incomplete_no_submission"
            assert result["counter"]["model_calls"] == 1  # host limit notice is not a paid model call
            assert not result["counter"]["incomplete_output"]  # this fixture model returned only tool calls
            assert result["counter"]["runtime_notices"]
            assert result["verifier"]["status"] == "review_submitted"
            assert result["verifier"]["model_calls"] == 2
            assert (await graph.aget_state(config)).values["counter"] == result["counter"]
            from apps.workbench.backend.api.v1.report_sessions import public_state
            assert "reasoning_content" not in json.dumps(public_state({"values": {"case_review": result}}))
            assert "recovery_state" not in json.dumps(public_state({"values": {"case_review": result}}))
    asyncio.run(exercise())


def test_review_returns_all_independent_quote_errors_at_once(artifacts):
    data = review_fixture(artifacts)
    data["findings"] = [{"finding_id": fid, "paper_id": "P01", "severity": "material",
        "problematic_quote": "SYNTHETIC MISSING QUOTE", "claim_ids": ["nonexistent"],
        "diagnosis": "Synthetic quote regression, not a financial finding.",
        "requested_change": "Correct all independent errors together.",
        "source_checks": [{"source_id": "P01:S001", "quote": "SYNTHETIC WRONG SOURCE QUOTE"},
                          {"source_id": "P99:S001", "quote": "missing source"}]}
        for fid in ("F1", "F2")]
    with pytest.raises(ValueError) as caught:
        validate_case_review(CaseReview.model_validate(data), artifacts, [])
    errors = json.loads(str(caught.value))["errors"]
    assert len(errors) == 9  # read coverage plus four independent errors per finding
    for fid in ("F1", "F2"):
        assert f"problematic_quote_not_exact:{fid}" in errors
        assert f"source_quote_not_exact:{fid}:P01:S001" in errors
        assert f"unknown_source_id:{fid}:P99:S001" in errors


def test_source_tool_scopes_hidden_and_injected(artifacts):
    async def exercise():
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            binding = await client.call_tool("get_dell_research_method", {"branch_ids": ["Q1_ISSUER_TRUTH"],
                "research_as_of": "2026-09-02T00:00:00Z", "data_snapshot_id": "fixture", "execution_attempt_id": "fixture"})
            assert not binding.is_error
            tools = await case_mcp_tools(client, run_scope=binding.structured_content["run_scope"])
            finance = next(t for t in tools if t.name == "query_company_financial_facts")
            assert "run_scope" not in finance.args
            assert finance.args["branch_id"]["enum"] == ["Q1_ISSUER_TRUTH"]
            assert "fiscal_year" in finance.args["granularity"]["enum"]
            assert "annual" not in finance.args["granularity"]["enum"]
            response = await finance.ainvoke(call("query_company_financial_facts", {
                "branch_id": "NOT_ALLOWED", "ticker": "DELL", "metric_ids": ["revenue"],
                "research_as_of": "2026-09-02", "granularity": "quarter_discrete", "selection_mode": "latest_on_or_before"}, "badbranch"))
            assert response.status == "error" and "branch_outside_case_scope" in response.content
    asyncio.run(exercise())
