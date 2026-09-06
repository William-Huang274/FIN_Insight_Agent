"""Agent Server resources for the current research-session product.

Uses the qualified Dell data bridge and existing role graphs. No qualification
runner, archived answer bundle, new provider transport, queue or checkpoint DB.
The browser selects a case/question, never file paths, budgets or credentials.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import UUID

from langchain_core.runnables import RunnableConfig, RunnableLambda
from langgraph.config import get_stream_writer
from langgraph_sdk.runtime import ServerRuntime
from mcp import Client
from pydantic import SecretStr

from .deepseek_structured_agents import (
    DeepSeekModelProfile, DeepSeekStructuredAgentAdapter, TokenBudgetBasis, load_deepseek_structured_agent_config,
)
from .dell_agent_server_data_composition import open_dell_approved_data_composition
from .dell_case_convergence_agent import build_case_output_agent
from .dell_case_review_agent import CaseModelAudit, build_case_review_graph, build_case_reviewer, case_chat_model, case_mcp_tools
from .dell_lead_research_graph import build_dell_lead_research_graph
from .dell_report_session import session_audit_sinks
from .dell_specialist_agentic_composition import open_dell_specialist_receipted_composition
from .research_session import build_research_session_graph, current_task_artifacts
from .research_convergence import build_research_convergence_graph


def load_research_runtime_profile(root):
    root = Path(root)
    profile = json.loads((root / "configs/research/runtime/research_session.json").read_text(encoding="utf-8"))
    required = {"lead", "specialist", "counter", "verifier", "repair", "synthesis", "research_verifier", "writer", "report_verifier", "quick_writer"}
    if set(profile["nodes"]) != required:
        raise ValueError("research_session_node_configuration_incomplete")
    for role, node in profile["nodes"].items():
        model = DeepSeekModelProfile.model_validate_json(json.dumps(node["profile"]))
        budget = TokenBudgetBasis.model_validate_json(json.dumps(node["budget"]))
        if budget.reasoning_profile != "agentic_message_history_thinking_" + model.thinking:
            raise ValueError("research_session_node_reasoning_budget_mismatch:" + role)
        if not 1 <= node["limits"]["model_calls"] <= 48 or not 1 <= node["limits"]["tool_calls"] <= 96:
            raise ValueError("research_session_node_capacity_invalid")
    case = json.loads((root / "configs/research/cases/dell_growth_quality.json").read_text(encoding="utf-8"))
    if not case["fresh_research"] or case["reuse_prior_workpapers"]:
        raise ValueError("fresh_research_profile_cannot_reuse_archived_answers")
    return profile, case


def create_research_phase_runnables(*, root, settings, profile, case, run_id, thread_id, api_key,
                                    environment=None, public_sink, private_sink):
    base = load_deepseek_structured_agent_config(Path(root) / profile["model_config"])
    invocation = "invocation:research-session:" + run_id
    research_id = "research-session:" + thread_id
    def emit(event):
        get_stream_writer()(event)
    def research_audit(event):
        public_sink(event)
        emit({"kind": "model", **event})
    def model_values(role):
        node = profile["nodes"][role]
        return DeepSeekModelProfile.model_validate_json(json.dumps(node["profile"])), TokenBudgetBasis.model_validate_json(json.dumps(node["budget"])), node["limits"]
    def research_config():
        updates = {r: model_values(r) for r in ("lead", "specialist")}
        return base.model_copy(update={"runtime_context_binding": True, "agentic_message_history": True,
            "model_profiles": {**base.model_profiles, **{r: row[0] for r, row in updates.items()}},
            "token_budget_basis": {**base.token_budget_basis, **{r: row[1] for r, row in updates.items()}}})

    async def research(request, config: RunnableConfig):
        configured = research_config()
        lead_adapter = DeepSeekStructuredAgentAdapter.from_config(config=configured, api_key=api_key,
            audit_sink=research_audit, private_audit_sink=private_sink)
        specialist_limits = profile["nodes"]["specialist"]["limits"]
        branches = case["branch_topics"]
        first_branch = branches[0]["branch_id"]
        with open_dell_specialist_receipted_composition(run_id=research_id, run_invocation_id=invocation,
                branch_id=first_branch, turn_source="provider_model", model_turn=lead_adapter.specialist_model_turn,
                environment=environment, source_read_enabled=True, live_web_read_enabled=True,
                max_model_turns=specialist_limits["model_calls"], max_tool_actions=specialist_limits["tool_calls"],
                research_question=request["question"]) as bootstrap:
            def worker(task, dependencies, child_config):
                task_event = {"kind": "task", "task_id": task["task_id"], "actor": task["owner_role"],
                    "objective": task["objective"], "dependency_ids": task["dependency_ids"],
                    "recorded_at": datetime.now(timezone.utc).isoformat()}
                emit({**task_event, "event": "started", "status": "running"})
                # A fresh provider history and read-only MCP lifecycle per child.
                adapter = DeepSeekStructuredAgentAdapter.from_config(config=configured, api_key=api_key,
                    audit_sink=research_audit, private_audit_sink=private_sink)
                try:
                    with open_dell_specialist_receipted_composition(run_id=research_id, run_invocation_id=invocation,
                            branch_id=task["coverage_obligation_ids"][0], turn_source="provider_model", model_turn=adapter.specialist_model_turn,
                            environment=environment, source_read_enabled=True, live_web_read_enabled=True,
                            max_model_turns=specialist_limits["model_calls"], max_tool_actions=specialist_limits["tool_calls"],
                            research_task=task, dependency_workpapers=dependencies, research_question=request["question"]) as child:
                        output = child.graph.invoke(child.graph_input.model_dump(mode="json"), {**child_config, "recursion_limit": 200})
                except Exception as exc:
                    emit({**task_event, "event": "outcome", "status": "error", "error_type": type(exc).__name__,
                          "recorded_at": datetime.now(timezone.utc).isoformat()})
                    raise
                emit({**task_event, "event": "outcome", "status": output["phase"],
                      "recorded_at": datetime.now(timezone.utc).isoformat()})
                return output
            graph = build_dell_lead_research_graph(expected_input=bootstrap.graph_input, research_question=request["question"],
                branch_catalog=branches, allowed_branch_ids=tuple(b["branch_id"] for b in branches), seed_workpapers={},
                model_turn=lead_adapter.lead_research_turn, run_child=worker,
                max_lead_turns=profile["nodes"]["lead"]["limits"]["model_calls"], max_tasks=profile["max_tasks"],
                max_parallel_tasks=profile["max_parallel_tasks"], turn_source="provider_model").compile()
            return await graph.ainvoke(bootstrap.graph_input.model_dump(mode="json"), {**config, "recursion_limit": 240})

    @asynccontextmanager
    async def tools_for(state):
        artifacts = current_task_artifacts(state)
        with open_dell_approved_data_composition(run_invocation_id=invocation, environment=environment,
                source_read_enabled=True, live_web_read_enabled=True, case_artifacts=artifacts) as data:
            if any(left != right for left, right in (
                (artifacts.case_id, data.foundation_binding.case_id), (artifacts.research_as_of, data.foundation_binding.research_as_of),
                (artifacts.snapshot_id, data.foundation_binding.snapshot_id), (artifacts.foundation_digest, data.foundation_binding.foundation_digest),
                (artifacts.owner_data_gate_decision_digest, data.decision_digest), (artifacts.inventory_snapshot_digest, data.inventory_snapshot_digest),
                (artifacts.source_route_catalog_digest, data.source_route_catalog_digest))):
                raise ValueError("research_session_task_data_binding_mismatch")
            async with Client(data.mcp_server, raise_exceptions=False, read_timeout_seconds=120) as client:
                binding = await client.call_tool("get_dell_research_method", {
                    "branch_ids": [row["branch_id"] for row in case["branch_topics"]],
                    "research_as_of": artifacts.research_as_of, "data_snapshot_id": artifacts.snapshot_id, "execution_attempt_id": invocation})
                if binding.is_error:
                    raise ValueError("research_session_data_method_binding_failed")
                # Host binds the frozen data scope; models read current role methods,
                # not an old top-level audit question via the legacy method tool.
                tools = await case_mcp_tools(client, run_scope=binding.structured_content["run_scope"])
                yield artifacts, tools

    def native_agent(role, tools, artifacts, *, feedback=None, paper_id=None, interactive=False, revising=False):
        model_profile, basis, limits = model_values(role)
        audit = CaseModelAudit(actor=("author_"+paper_id if paper_id else role), profile=model_profile, basis=basis,
            public_sink=public_sink, private_sink=private_sink, stream_public=True)
        model = case_chat_model(model_profile, basis, base, api_key)
        if role in {"counter", "verifier"}:
            return build_case_reviewer(role=role, model=model, tools=tools, artifacts=artifacts,
                max_model_calls=limits["model_calls"], max_tool_calls=limits["tool_calls"], audit=audit)
        output_role = ("verifier" if role in {"report_verifier", "research_verifier"} else "writer" if role in {"writer", "quick_writer"}
                       else "synthesis" if role == "synthesis" else "repair")
        return build_case_output_agent(role=output_role, model=model, tools=tools, artifacts=artifacts,
            feedback=feedback, paper_id=paper_id, limits=limits, audit=audit, report_revision=interactive or revising,
            allow_answers=interactive and output_role == "writer", answer_only=role == "quick_writer",
            require_responsibility=role in {"report_verifier", "research_verifier"})

    async def review(state, config: RunnableConfig):
        async with tools_for(state) as (artifacts, tools):
            reviewers = {role: native_agent(role, tools, artifacts) for role in ("counter", "verifier")}
            graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question=state["question"],
                run_id=research_id, run_invocation_id=invocation).compile()
            return await graph.ainvoke({"run_id": research_id, "run_invocation_id": invocation}, config)

    async def execute_convergence(state, config, existing=None):
        async with tools_for(state) as (artifacts, tools):
            def make_agent(role, current, *, feedback=None, paper_id=None, correction_round=0, revising_report=False):
                return native_agent(role, tools, current, feedback=feedback, paper_id=paper_id,
                    revising=role == "writer" and revising_report)
            graph = build_research_convergence_graph(artifacts=artifacts, question=state["question"], feedback=state["feedback"],
                make_agent=make_agent, max_parallel_authors=profile["max_parallel_tasks"],
                research_review_context={**{r: state["case_review"][r]["review"] for r in ("counter", "verifier")},
                    "lead_handoff": state.get("research_handoff")}, existing_state=existing,
                human_feedback=existing.get("message") if existing else None).compile()
            return await graph.ainvoke({}, config)

    async def converge(state, config: RunnableConfig):
        return await execute_convergence(state, config)

    async def revise_research(state, config: RunnableConfig):
        return await execute_convergence({**state, "feedback": {}}, config, existing=state)

    def interactive(role):
        async def execute(state, config: RunnableConfig):
            async with tools_for(state) as (artifacts, tools):
                agent = native_agent(role, tools, artifacts, interactive=True)
                return await agent.ainvoke({key: value for key, value in state.items() if key != "case_papers"}, config)
        return RunnableLambda(execute)

    return {"research": RunnableLambda(research), "review": RunnableLambda(review), "converge": RunnableLambda(converge),
            "revise_research": RunnableLambda(revise_research), "writer": interactive("writer"),
            "verifier": interactive("report_verifier"), "quick_writer": interactive("quick_writer")}


@asynccontextmanager
async def research_session_graph(config: RunnableConfig, runtime: ServerRuntime):
    if runtime.execution_runtime is None:
        def unavailable(_):
            raise RuntimeError("schema_only_execution_unavailable")
        phases = {key: RunnableLambda(unavailable) for key in ("research", "review", "converge", "writer", "verifier", "quick_writer", "revise_research")}
        yield build_research_session_graph(**phases).compile(name="research_session")
        return
    from .dell_agent_server_entry import _require_langsmith_execution_environment
    _require_langsmith_execution_environment(config)
    if os.environ.get("FINSIGHT_RESEARCH_SESSION_ENABLED") != "1":
        raise ValueError("fresh_research_deployment_not_enabled")
    ids = config["configurable"]
    thread_id, run_id = str(UUID(str(ids["thread_id"]))), str(UUID(str(ids["run_id"])))
    root = Path(os.environ["FIN_REPO_ROOT"])
    settings = json.loads(Path(os.environ["FINSIGHT_REPORT_SESSION_SETTINGS"]).read_text(encoding="utf-8"))
    profile, case = load_research_runtime_profile(root)
    public, private = session_audit_sinks(Path(settings["audit_root"]) / thread_id / run_id)
    phases = create_research_phase_runnables(root=root, settings=settings, profile=profile, case=case,
        thread_id=thread_id, run_id=run_id, api_key=SecretStr(os.environ["DEEPSEEK_API_KEY"]), public_sink=public, private_sink=private)
    yield build_research_session_graph(**phases).compile(name="research_session").with_config({"recursion_limit": 280})
