"""Agent Server resources for the current research-session product.

Uses the qualified Dell data bridge and existing role graphs. No qualification
runner, archived answer bundle, new provider transport, queue or checkpoint DB.
The browser selects a case/question, never file paths, budgets or credentials.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
from threading import Event
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import UUID


from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import StructuredTool, tool, ToolException
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.prebuilt import ToolRuntime
from langgraph.config import get_stream_writer
from langgraph_sdk.runtime import ServerRuntime
from mcp import Client
from pydantic import SecretStr, BaseModel, Field

from .deepseek_structured_agents import (
    DeepSeekModelProfile, DeepSeekStructuredAgentAdapter, TokenBudgetBasis, load_deepseek_structured_agent_config,
)
from .agent_server_data_composition import open_approved_data_composition
from .report_synthesis_agent import build_case_output_agent
from .case_review_agent import CaseModelAudit, build_case_review_graph, build_case_reviewer, case_chat_model, case_mcp_tools
from .lead_research_graph import build_lead_research_graph
from .report_session import session_audit_sinks
from .specialist_composition import open_specialist_receipted_composition
from .research_session import build_research_session_graph, current_task_artifacts
from .research_convergence import build_research_convergence_graph
from .studio_configuration import configuration_from_native
from .execution_options import ExecutionOptions, execution_from_config


def cancellable_model_turn(turn, cancelled):
    """Retain an in-flight receipt but stop cancelled synchronous workers."""
    def invoke(request):
        if cancelled.is_set():
            raise RuntimeError('research_cancelled_before_model_call')
        response = turn(request)
        if cancelled.is_set():
            raise RuntimeError('research_cancelled_after_model_call')
        return response
    return invoke


def block_unknown_model_inputs(turn, blocked_digests):
    """An operator continuation cannot resend an unresolved semantic input."""
    from .deepseek_structured_agents import _project_request, canonical_sha256
    def invoke(request):
        semantic = _project_request('specialist', request, specialist_mode='agentic_turn')
        if canonical_sha256(semantic) in blocked_digests:
            raise RuntimeError('unresolved_model_input_resend_blocked')
        return turn(request)
    return invoke


class ResearchProgress(BaseModel):
    message: str = Field(min_length=1, max_length=1200, description="面向研究者的简短进展：正在核对什么、已观察到什么、接下来做什么。不是私有思维链，不粘贴原文或凭据。")


def load_research_runtime_profile(root):
    root = Path(root)
    profile = json.loads((root / "configs/research/runtime/research_session.json").read_text(encoding="utf-8"))
    required = {"lead", "specialist", "counter", "verifier", "repair", "synthesis", "research_verifier", "writer", "report_verifier", "quick_writer"}
    if set(profile["nodes"]) != required:
        raise ValueError("research_session_node_configuration_incomplete")
    editing = profile.get("context_editing")
    if editing is not None and (not {"trigger_tokens", "keep"}.issubset(editing)
            or set(editing) - {"trigger_tokens", "keep", "policy", "checkpoint_trigger_tokens", "checkpoint_reserve_tokens"}
            or editing.get("policy", "legacy_window") not in {"legacy_window", "task_boundary"}
            or type(editing["trigger_tokens"]) is not int or editing["trigger_tokens"] < 1
            or type(editing["keep"]) is not int or not 1 <= editing["keep"] <= 64):
        raise ValueError("research_session_context_editing_configuration_invalid")
    if editing and any(type(editing[k]) is not int or editing[k] < 1
            for k in ("checkpoint_trigger_tokens", "checkpoint_reserve_tokens") if k in editing):
        raise ValueError("research_session_context_checkpoint_configuration_invalid")
    if editing and "checkpoint_trigger_tokens" in editing and editing.get("policy") != "task_boundary":
        raise ValueError("research_session_context_checkpoint_requires_task_boundary")
    summary = profile.get("context_summarization")
    if summary:
        if (set(summary) != {"enabled", "trigger_tokens", "keep_tokens", "max_summaries", "profile", "budget"}
                or type(summary["enabled"]) is not bool
                or any(type(summary[k]) is not int for k in ("trigger_tokens", "keep_tokens", "max_summaries"))
                or not 0 < summary["keep_tokens"] < summary["trigger_tokens"]
                or not 1 <= summary["max_summaries"] <= 2):
            raise ValueError("research_session_summary_configuration_invalid")
        summary_model = DeepSeekModelProfile.model_validate_json(json.dumps(summary["profile"]))
        summary_basis = TokenBudgetBasis.model_validate_json(json.dumps(summary["budget"]))
        if summary_basis.reasoning_profile != "agentic_message_history_thinking_" + summary_model.thinking:
            raise ValueError("research_session_summary_reasoning_budget_mismatch")
    for role, node in profile["nodes"].items():
        model = DeepSeekModelProfile.model_validate_json(json.dumps(node["profile"]))
        budget = TokenBudgetBasis.model_validate_json(json.dumps(node["budget"]))
        if budget.reasoning_profile != "agentic_message_history_thinking_" + model.thinking:
            raise ValueError("research_session_node_reasoning_budget_mismatch:" + role)
        if not 1 <= node["limits"]["model_calls"] <= 48 or not 1 <= node["limits"]["tool_calls"] <= 96:
            raise ValueError("research_session_node_capacity_invalid")
    case = json.loads((root / "configs/research/cases/growth_quality.json").read_text(encoding="utf-8"))
    if not case["fresh_research"] or case["reuse_prior_workpapers"]:
        raise ValueError("fresh_research_profile_cannot_reuse_archived_answers")
    return profile, case


def create_research_phase_runnables(*, root, settings, profile, case, run_id, thread_id, api_key,
                                    environment=None, public_sink, private_sink, read_guidance=None, studio=None, execution=None,
                                    blocked_model_inputs=(), plan_invocation_id=None, budget_scope=None, author_audit_paths=()):
    if studio:
        profile = studio.apply_profile(profile)
        case = studio.apply_case(case)
    execution = execution or ExecutionOptions()
    execution.validate_catalog(case["branch_topics"])
    profile = execution.apply_profile(profile)
    environment = {**(os.environ if environment is None else environment), "FINSIGHT_TASK_THREAD_ID": thread_id,
        "FINSIGHT_TASK_RUN_ID": run_id, "FINSIGHT_TASK_AUDIT_ROOT": settings["audit_root"]}
    # The same host-approved, mounted fact snapshot serves both entry points.
    # Frozen Dell source inventories and historical result bindings stay intact.
    if settings.get('conversation_fact_mart'):
        environment['FINSIGHT_RESEARCH_FACT_MART_PATH'] = str(Path(settings['conversation_fact_mart']).resolve(strict=True))
    base = load_deepseek_structured_agent_config(Path(root) / profile["model_config"])
    invocation = "invocation:research-session:" + run_id
    research_id = "research-session:" + thread_id
    cancelled = Event()
    def emit(event):
        event = {"recorded_at": datetime.now(timezone.utc).isoformat(), **event}
        # Redis stream retention is not a durable task history. Reuse the
        # existing public audit sink; never expose child message histories.
        if event.get("kind") in {"task", "stage"}:
            public_sink(event)
        get_stream_writer()(event)
    def visible_turn(turn, actor, task_id=None):
        if blocked_model_inputs:
            turn = block_unknown_model_inputs(turn, blocked_model_inputs)
        turn = cancellable_model_turn(turn, cancelled)
        def invoke(request):
            progress = (request.get("task_context") or {}).get("runtime_progress", {})
            if progress.get("status") == "warn":
                emit({"kind": "stage", "actor": actor, "event": "progress", "task_id": task_id,
                    "status": "no_new_observations", "objective": "连续读取未增加新的观察，runtime已提示专家核对已读结果、调整检索或研究步骤；持续卡住将交给Lead协助。"})
            response = turn(request)
            for call in response.get("action", {}).get("tool_calls", []):
                args = call.get("args")
                from .public_research_output import submitted_prose
                prose = submitted_prose(call.get("name"), args)
                if prose:
                    emit({"kind": "stage", "actor": actor, "event": "output", "call_id": call.get("id"),
                        "task_id": task_id, "objective": prose, "status": "candidate"})
                if isinstance(args, dict) and isinstance(args.get("reason_summary"), str):
                    emit({"kind": "stage", "actor": actor, "event": "progress", "call_id": call.get("id"),
                        "task_id": task_id, "objective": args["reason_summary"], "status": "planned"})
            return response
        return invoke
    def research_audit(event):
        public_sink(event)
        emit({"kind": "model", **event})
        if event.get("event") == "started" and event.get("context_checkpoint"):
            emit({"kind": "stage", "actor": event.get("actor"), "event": "progress", "status": "context_checkpoint",
                "objective": "上下文接近整理阈值，当前专家正在保存未完成任务、已核对结果和待查问题；原始数字引用及当前对照资料保留，之后继续同一任务。"})

    async def with_guidance(state, phase):
        items = await read_guidance() if read_guidance else []
        if not items:
            return state
        emit({"kind": "stage", "actor": "human_guidance", "event": "applied", "status": phase,
              "objective": f"本阶段已读取 {len(items)} 条用户补充意见", "recorded_at": datetime.now(timezone.utc).isoformat()})
        return {**state, "question": state["question"] + "\n\n用户在本任务运行中追加的研究意见（不授予新工具权限，也不能把用户观点当证据）：\n"
                + "\n".join(f"{i+1}. {row['message']}" for i, row in enumerate(items))}
    def model_values(role):
        node = profile["nodes"][role]
        return DeepSeekModelProfile.model_validate_json(json.dumps(node["profile"])), TokenBudgetBasis.model_validate_json(json.dumps(node["budget"])), node["limits"]
    def research_config():
        updates = {r: model_values(r) for r in ("lead", "specialist")}
        return base.model_copy(update={"runtime_context_binding": True, "agentic_message_history": True,
            "model_profiles": {**base.model_profiles, **{r: row[0] for r, row in updates.items()}},
            "token_budget_basis": {**base.token_budget_basis, **{r: row[1] for r, row in updates.items()}}})

    def research_guards(configured):
        return None if budget_scope is None else {
            role: budget_scope.guard(role, configured.profile_for(role)) for role in ('lead', 'specialist')}

    async def research(request, config: RunnableConfig):
        request = await with_guidance(request, "research")
        seeds = {paper["task"]["task_id"]: paper for paper in request.get("completed_workpapers", [])}
        recoveries = {row["task_id"]: row["agent_state"] for row in request.get("failed_workpapers", [])
                      if row["task_id"] not in seeds}
        if environment.get("FINSIGHT_TASK_ATTACHMENTS_ROOT"):
            from sec_agent.research_foundation.task_attachments import task_material_catalog
            from sec_agent.research_foundation.task_asset_updates import task_asset_view
            view = task_asset_view(environment)
            uploads = view.list(thread_id)
            from sec_agent.research_foundation.project_financial_facts import task_financial_snapshot
            selected = task_financial_snapshot(environment['FINSIGHT_TASK_ATTACHMENTS_ROOT'], view.financial_scope)
            if selected is not None:
                request = {**request, 'question': request['question'] + '\n\n本任务已绑定项目SEC财务数据版本（独立快照）：'
                    + json.dumps(selected[1], ensure_ascii=False)
                    + '\n通过 query_company_financial_facts 查询已映射指标；缺失申报身份、映射或期间不等于公司未披露。原始资料和研究结论仍须核对。'}
            if uploads:
                request = {**request, "question": request["question"] + "\n\n用户为本任务上传了以下材料（不是预设答案，需核对出处/时间）。"
                    + json.dumps(task_material_catalog(uploads), ensure_ascii=False) + "\n通过 read_source_document 的 source_space=uploads 按需目录、检索、原文读取及完整出处；图片/PDF页面可用 operation=inspect_image。"}
        configured = research_config()
        lead_adapter = DeepSeekStructuredAgentAdapter.from_config(config=configured, api_key=api_key,
            audit_sink=research_audit, private_audit_sink=private_sink, context_editing=profile.get("context_editing"),
            dispatch_guards=research_guards(configured), source_access_check=source_access_check)
        specialist_limits = profile["nodes"]["specialist"]["limits"]
        branches = [b for b in case["branch_topics"] if not execution.branch_ids or b["branch_id"] in execution.branch_ids]
        first_branch = branches[0]["branch_id"]
        with open_specialist_receipted_composition(run_id=research_id, run_invocation_id=invocation,
                plan_invocation_id=plan_invocation_id,
                branch_id=first_branch, turn_source="provider_model", model_turn=visible_turn(lead_adapter.specialist_model_turn, "specialist"),
                role_method_reader=studio.method if studio else None,
                role_method=studio.specialist_method([first_branch]) if studio else None,
                environment=environment, source_read_enabled=True, live_web_read_enabled=True,
                max_model_turns=specialist_limits["model_calls"], max_tool_actions=specialist_limits["tool_calls"],
                research_question=request["question"],
                recovery_state=next(iter(recoveries.values()), None) if execution.mode == "single" else None) as bootstrap:
            if execution.mode == "single":
                emit({"kind": "stage", "actor": "specialist", "event": "started", "objective": "按所选方向独立研究；不启动负责人分派或其他审查 Agent。"})
                output = await bootstrap.graph.ainvoke(bootstrap.graph_input.model_dump(mode="json"), {**config, "recursion_limit": 200})
                task_id = output["task"]["task_id"]
                submitted = output.get("final_submission") is not None
                return {"phase": "research_ready_for_review" if submitted else "research_needs_attention",
                    "tasks": [{"task_id": task_id, "owner_role": "specialist", "objective": request["question"], "dependency_ids": []}],
                    "task_results": [{"task_id": task_id, "status": "submitted" if submitted else "needs_attention", "agent_state": output}],
                    "lead_handoff": None, "stop_reason": None if submitted else "single_agent_no_submission"}
            def worker(task, dependencies, child_config, *, helper=False):
                # Native checkpoints can retain a child queued by an older
                # planner. Recheck current continuation authority before any
                # adapter/provider call, not just when creating a new task.
                if seeds and not helper and task['task_id'] not in {t['task_id'] for t in request.get('unfinished_tasks', [])}:
                    raise ValueError('continuation_queued_task_outside_original_scope')
                task_event = {"kind": "task", "task_id": task["task_id"], "actor": task["owner_role"],
                    "objective": task["objective"], "dependency_ids": task["dependency_ids"],
                    "recorded_at": datetime.now(timezone.utc).isoformat()}
                emit({**task_event, "event": "started", "status": "running"})
                def run_subtask(spec, parent_state, nested_config):
                    nested_task = {**task, "task_id": task["task_id"] + "/sub/" + spec["subtask_id"],
                        "objective": spec["objective"], "success_criteria": spec["success_criteria"], "dependency_ids": []}
                    # Separate native specialist context; no entire parent question,
                    # notebook or sibling message history is copied into the helper.
                    nested_task["objective"] += "\n来源导航/待查方向：" + json.dumps(spec["source_hints"], ensure_ascii=False)
                    return worker(nested_task, {}, nested_config, helper=True)
                def help_blocked_expert(state, help_config):
                    from .research_assistance import build_lead_assistance_graph
                    from .research_graph_contracts import canonical_sha256
                    emit({**task_event, "event": "progress", "status": "lead_assistance",
                        "objective": "研究执行遇到阻塞，已通知研究负责人检查当前状态、上下文负担和来源导航，协助调整研究方法。"})
                    basis = configured.token_budget_basis["lead"].model_copy(update={
                        "node_purpose": "Lead diagnoses the current blocked expert using its original assignment, actual observations and working state; source-check a changed recovery approach or stop, without replacing the task.",
                        "required_outputs": ("A concrete diagnosis, next approach, expected progress or explicit unresolved stop; preserve current task authority and lifetime limits.",)})
                    help_configured = configured.model_copy(update={"token_budget_basis": {**configured.token_budget_basis, "lead": basis}})
                    help_adapter = DeepSeekStructuredAgentAdapter.from_config(config=help_configured, api_key=api_key,
                        audit_sink=research_audit, private_audit_sink=private_sink, context_editing=profile.get("context_editing"),
                        dispatch_guards=research_guards(help_configured), source_access_check=source_access_check)
                    observations = [{"status": o["status"], "references": o["references"],
                        "navigation": [{k: item[k] for k in ("node_id", "document_id", "document_navigation", "section_path") if k in item}
                            for item in o.get("content", []) if isinstance(item, dict)]} for o in state["notebook"]["observations"]]
                    request_base = {"agent_id": "lead:assistance:" + canonical_sha256(task["task_id"])[:16] + ":" + str(len(state.get("lead_assistance_history", []))),
                        "research_question": request["question"], "research_as_of": state["task"]["research_as_of"],
                        "branch_catalog": [b for b in branches if b["branch_id"] in task["coverage_obligation_ids"]],
                        "required_branch_ids": list(task["coverage_obligation_ids"]),
                        "capabilities": child.graph_input.l0_context.capability_summaries,
                        "capacity": {"max_lead_turns": 4, "max_tasks": 0, "max_parallel_tasks": 1},
                        "tasks": [task], "workpapers": [{"task_id": task["task_id"], "working_state": state.get("research_working_state"),
                            "runtime_progress": state.get("runtime_progress"), "observations": observations,
                            "prior_assistance": state.get("lead_assistance_history", [])}],
                        "scope_policy": "Help this original task only; source access/cutoff and root budget are unchanged."}
                    spaces = {s for row in child.graph_input.l0_context.capability_summaries for s in row.get("source_spaces", [])}
                    graph = build_lead_assistance_graph(request_base=request_base,
                        model_turn=cancellable_model_turn(help_adapter.lead_research_turn, cancelled), source_reader=child.source_reader,
                        source_spaces=spaces).compile()
                    result = graph.invoke({}, {**help_config, "recursion_limit": 16})["guidance"]
                    emit({**task_event, "event": "progress", "status": "lead_guidance_received", "objective": result["next_action"]})
                    return result
                # A fresh provider history and read-only MCP lifecycle per child.
                adapter = DeepSeekStructuredAgentAdapter.from_config(config=configured, api_key=api_key,
                    audit_sink=research_audit, private_audit_sink=private_sink, context_editing=profile.get("context_editing"),
                    dispatch_guards=research_guards(configured), source_access_check=source_access_check)
                try:
                    with open_specialist_receipted_composition(run_id=research_id, run_invocation_id=invocation,
                            plan_invocation_id=plan_invocation_id,
                            branch_id=task["coverage_obligation_ids"][0], turn_source="provider_model", model_turn=visible_turn(adapter.specialist_model_turn, task["owner_role"], task["task_id"]),
                            role_method_reader=studio.method if studio else None,
                            role_method=studio.specialist_method(task['coverage_obligation_ids']) if studio else None,
                            environment=environment, source_read_enabled=True, live_web_read_enabled=True,
                            max_model_turns=specialist_limits["model_calls"], max_tool_actions=specialist_limits["tool_calls"],
                            recovery_state=recoveries.get(task["task_id"]),
                            research_task=task, dependency_workpapers=dependencies,
                            subtask_runner=None if helper else run_subtask,
                            working_state_enabled=True, lead_assistance=help_blocked_expert,
                            research_question=(task["objective"] + "\n你负责这个独立子问题；提交前自检数字、引用及正文的一致性，报告限制，不再委派。") if helper else request["question"]) as child:
                        output = child.graph.invoke(child.graph_input.model_dump(mode="json"), {**child_config, "recursion_limit": 200})
                except Exception as exc:
                    from .task_outcome import task_outcome
                    emit({**task_event, "event": "outcome", "status": "error", "error_type": type(exc).__name__,
                          "task_outcome": task_outcome({"run_id": research_id, "run_invocation_id": invocation},
                              assignment=task, error_type=type(exc).__name__, cancelled=cancelled.is_set()),
                          "recorded_at": datetime.now(timezone.utc).isoformat()})
                    raise
                from .task_outcome import task_outcome
                emit({**task_event, "event": "outcome", "status": output["phase"],
                      "task_outcome": task_outcome(output, assignment=task),
                      "recorded_at": datetime.now(timezone.utc).isoformat()})
                return output
            graph = build_lead_research_graph(expected_input=bootstrap.graph_input, research_question=request["question"],
                hierarchical=True,
                source_reader=bootstrap.source_reader,
                branch_catalog=branches, allowed_branch_ids=tuple(b["branch_id"] for b in branches), seed_workpapers=seeds,
                model_turn=cancellable_model_turn(lead_adapter.lead_research_turn, cancelled), run_child=worker,
                require_all_branches=execution.mode != "auto", public_progress=emit, require_execution_plan=True,
                recovery_tasks=request.get("unfinished_tasks", []),
                role_method=studio.method(studio.bindings["lead"]) if studio else None,
                max_lead_turns=profile["nodes"]["lead"]["limits"]["model_calls"], max_tasks=profile["max_tasks"],
                max_parallel_tasks=profile["max_parallel_tasks"], turn_source="provider_model", unfinished_only=bool(seeds)).compile()
            return await graph.ainvoke(bootstrap.graph_input.model_dump(mode="json"), {**config, "recursion_limit": 240})

    @asynccontextmanager
    async def tools_for(state, artifacts_override=None):
        artifacts = artifacts_override if artifacts_override is not None else current_task_artifacts(state)
        with open_approved_data_composition(run_invocation_id=invocation, environment=environment,
                source_read_enabled=True, live_web_read_enabled=True, case_artifacts=artifacts,
                role_method_reader=studio.method if studio else None) as data:
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

    from sec_agent.research_foundation.project_asset_access import task_access_check
    source_access_check = task_access_check(environment)

    def native_agent(role, tools, artifacts, *, feedback=None, paper_id=None, interactive=False, revising=False, actor_override=None, confirmation=None, incomplete_reviewers=None, review_execution_control=None):
        if role == "repair" and execution.mode == "selected":
            branch = next((p["branch_id"] for p in artifacts.catalog()["papers"] if p["paper_id"] == paper_id), None)
            if branch not in execution.branch_ids:
                raise ValueError("所需修订超出所选研究方向；请扩大范围后发起新运行")
        profile_role = "synthesis" if role == "lead_decision" else role
        method_instructions = studio.instructions(profile_role) if studio else ""
        async def report_progress(message: str):
            emit({"kind": "stage", "actor": actor_override or ("author_" + paper_id if paper_id else role),
                "event": "progress", "objective": message})
            return "进展已展示给研究者；不是证据或阶段完成。"
        progress_tool = StructuredTool.from_function(coroutine=report_progress, name="report_research_progress",
            description="Send a concise public progress update in the user's language (Chinese for a Chinese question) at a meaningful change of work. Do not expose private chain of thought, repeat every tool result, or claim unverified completion.", args_schema=ResearchProgress)
        tools = [*tools, progress_tool]
        method_instructions += "\nUse report_research_progress to briefly tell the researcher your approach before substantial work, and significant findings or a changed plan. Keep it concise and public; do not narrate hidden reasoning or call it after every tool."
        model_profile, basis, limits = model_values(profile_role)
        if role == "lead_decision":
            basis = basis.model_copy(update={
                "node_purpose": "Research Lead inspects current paper versions and independent findings before final judgment; assign targeted repairs, substantiate disagreements, discover missed issues or stop unresolved work.",
                "required_outputs": ("One disposition per original finding and explicit new findings, responsible papers, source-bound reasons, requested changes and expected progress; no final report or automatic acceptance.",),
                "input_scale": "Current question, compact version/issue navigation, independent findings, and current papers/original sources read on demand; no specialist private histories."})
            if incomplete_reviewers is not None:
                basis = basis.model_copy(update={
                    'node_purpose': 'Lead diagnoses incomplete review from saved public findings and exact tool errors, without restarting research or accepting the paper.',
                    'required_outputs': ('One bounded outstanding-check assignment per incomplete reviewer, with expected progress and stop condition; or explicit stop. No report or author-edit execution.',)})
        audit = CaseModelAudit(actor=actor_override or ("author_"+paper_id if paper_id else role), profile=model_profile, basis=basis,
            public_sink=public_sink, private_sink=private_sink, stream_public=True,
            dispatch_guard=budget_scope.guard(profile_role, model_profile) if budget_scope else None, source_access_check=source_access_check)
        audit.review_execution_control = review_execution_control
        if any(t.name == "consult_research_specialist" for t in tools):
            from langchain.agents.middleware import ToolCallLimitMiddleware
            audit.extra_middlewares = [ToolCallLimitMiddleware(tool_name="consult_research_specialist", run_limit=2, exit_behavior="error")]
        model = case_chat_model(model_profile, basis, base, api_key, context_editing=profile.get("context_editing"))
        summary = profile.get("context_summarization")
        if summary and summary["enabled"] and role != "quick_writer":
            from .model_context import RequestSummaryMiddleware
            summary_profile = DeepSeekModelProfile.model_validate_json(json.dumps(summary["profile"]))
            summary_basis = TokenBudgetBasis.model_validate_json(json.dumps(summary["budget"]))
            summary_model = case_chat_model(summary_profile, summary_basis, base, api_key)
            summary_audit = CaseModelAudit(actor="context_summary:" + audit.actor, profile=summary_profile,
                basis=summary_basis, public_sink=public_sink, private_sink=private_sink, stream_public=True,
                dispatch_guard=budget_scope.guard('context_summary', summary_profile) if budget_scope else None, source_access_check=source_access_check)
            summary_audit.review_execution_control = review_execution_control
            audit.context_summary = RequestSummaryMiddleware(model=summary_model,
                audited_model=summary_audit.model_runnable(summary_model), trigger_tokens=summary["trigger_tokens"],
                keep_tokens=summary["keep_tokens"], max_summaries=summary["max_summaries"])
        if role in {"counter", "verifier"}:
            return build_case_reviewer(role=role, model=model, tools=tools, artifacts=artifacts,
                max_model_calls=limits["model_calls"], max_tool_calls=limits["tool_calls"], audit=audit,
                method_instructions=method_instructions, confirmation=confirmation, require_inspection=confirmation is None)
        output_role = ("verifier" if role in {"report_verifier", "research_verifier"} else "writer" if role in {"writer", "quick_writer"}
                       else "synthesis" if role == "synthesis" else "decision" if role == "lead_decision" else "repair")
        return build_case_output_agent(role=output_role, model=model, tools=tools, artifacts=artifacts,
            feedback=feedback, paper_id=paper_id, limits=limits, audit=audit, report_revision=interactive or revising,
            allow_answers=interactive and output_role == "writer", answer_only=role == "quick_writer",
            require_responsibility=role in {"report_verifier", "research_verifier"}, method_instructions=method_instructions,
            incomplete_reviewers=incomplete_reviewers)

    async def review(state, config: RunnableConfig):
        state = await with_guidance(state, "review")
        async with tools_for(state) as (artifacts, tools):
            from .review_execution import ReviewExecutionControl
            control = ReviewExecutionControl()
            reviewers = {role: native_agent(role, tools, artifacts, review_execution_control=control) for role in ("counter", "verifier")}
            graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question=state["question"],
                run_id=research_id, run_invocation_id=invocation,
                review_order=studio.review_order if studio else "parallel",
                research_handoff=state.get("research_handoff"), previous_review=state.get("previous_review"),
                recovery_instructions=state.get('review_recovery_instructions'), require_inspection=True).compile()
            return await graph.ainvoke({"run_id": research_id, "run_invocation_id": invocation}, config)

    async def triage_review(state, config: RunnableConfig):
        state = await with_guidance(state, 'lead_review_triage')
        from .review_recovery import review_recovery_handoff
        async with tools_for(state) as (artifacts, tools):
            handoff = review_recovery_handoff(state['case_review'], artifacts, state['question'])
            agent = native_agent('lead_decision', tools, artifacts, feedback=handoff['feedback'],
                actor_override='lead_review_triage', incomplete_reviewers=handoff['incomplete_reviewers'])
            result = await agent.ainvoke({'messages': [HumanMessage(content=json.dumps({
                'question': state['question'], 'catalog': artifacts.catalog(), 'incomplete_review_handoff': handoff}, ensure_ascii=False))],
                'revisions': state.get('revisions', {})}, config)
            output = result.get('output')
            if not output or output.get('kind') != 'lead_issue_decision':
                return {'action': 'stop', 'decision_source':'runtime_incomplete_lead',
                    'summary': 'Lead did not submit a valid bounded review recovery decision; runtime stopped without report acceptance.',
                    'tool_feedback':[m.content for m in result.get('messages',[]) if isinstance(m,ToolMessage) and m.status=='error'][-4:]}
            return output

    async def execute_convergence(state, config, existing=None):
        state = await with_guidance(state, "convergence")
        async with tools_for(state) as (artifacts, tools):
            async def run_author(paper_id, convergence_state, child_config):
                from .author_revision import current_author_state, restore_author_history, native_revision_view, author_feedback
                from .task_outcome import task_outcome
                saved = current_author_state(artifacts, paper_id, convergence_state.get("revisions", {}))
                assignment = saved.get("task_context", {}).get("assignment")
                if not assignment:
                    raise ValueError("original_author_assignment_unavailable")
                if execution.mode == "selected" and saved["task"]["branch_id"] not in execution.branch_ids:
                    raise ValueError("author_revision_outside_selected_scope")
                repair_profile, basis, limits = model_values("repair")
                configured = research_config().model_copy(update={
                    "model_profiles": {**research_config().model_profiles, "specialist": repair_profile},
                    "token_budget_basis": {**research_config().token_budget_basis, "specialist": basis.model_copy(update={"node_role": "specialist"})}})
                adapter = DeepSeekStructuredAgentAdapter.from_config(config=configured, api_key=api_key,
                    audit_sink=research_audit, private_audit_sink=private_sink, context_editing=profile.get("context_editing"),
                    dispatch_guards={"specialist": budget_scope.guard("repair", repair_profile)} if budget_scope else None,
                    source_access_check=source_access_check)
                paths = [*author_audit_paths, *(Path(settings["audit_root"]) / thread_id).glob("*/model-context-reasoning.private.jsonl")]
                restore_author_history(adapter, saved, paths)
                current = artifacts.with_revisions(convergence_state.get("revisions", {}))
                findings = author_feedback(convergence_state["pending_feedback"][paper_id], current)
                dependencies = {row["task"]["task_id"]: row for row in current._author_states.values()
                    if row["task"]["task_id"] in assignment.get("dependency_ids", [])}
                if set(dependencies) != set(assignment.get("dependency_ids", [])):
                    raise ValueError("original_author_dependency_handoff_unavailable")
                async def resume():
                    with open_specialist_receipted_composition(run_id=saved["run_id"], run_invocation_id=invocation,
                            plan_invocation_id=plan_invocation_id, branch_id=saved["task"]["branch_id"],
                            turn_source="provider_model", model_turn=visible_turn(adapter.specialist_model_turn, saved["agent_id"], assignment["task_id"]),
                            environment=environment, source_read_enabled=True, live_web_read_enabled=True,
                            research_task=assignment, dependency_workpapers=dependencies,
                            research_question=state["question"], recovery_state=saved,
                            revision_feedback=findings, required_source_checks=saved.get("required_source_checks", []),
                            max_model_turns=limits["model_calls"], max_tool_actions=limits["tool_calls"],
                            working_state_enabled=True, role_method_reader=studio.method if studio else None) as opened:
                        return await opened.graph.ainvoke(opened.graph_input.model_dump(mode="json"), {**child_config, "recursion_limit": 200})
                output = await resume()
                emit({"kind": "task", "event": "outcome", "actor": saved["agent_id"], "task_id": assignment["task_id"],
                    "status": output["phase"], "task_outcome": task_outcome(output, assignment=assignment)})
                if output["phase"] != "specialist_submission_accepted":
                    raise ValueError("original_author_revision_incomplete:" + str(output.get("review_reason")))
                return native_revision_view(output, current, paper_id, findings)

            async def review_revisions(current, context, child_config):
                # A fresh data view is essential: MCP readers and calculators
                # must see the same current candidate the review validator sees.
                async with tools_for(state, current) as (_, current_tools):
                    from .review_execution import ReviewExecutionControl
                    control = ReviewExecutionControl()
                    reviewers = {role: native_agent(role, current_tools, current, confirmation=context,
                        actor_override="confirmation_" + role, review_execution_control=control) for role in ("counter", "verifier")}
                    graph = build_case_review_graph(reviewers=reviewers, artifacts=current, question=state["question"],
                        run_id=research_id, run_invocation_id=invocation, confirmation=context,
                        review_order=studio.review_order if studio else "parallel").compile()
                    return await graph.ainvoke({"run_id": research_id, "run_invocation_id": invocation}, child_config)

            def make_agent(role, current, *, feedback=None, paper_id=None, correction_round=0, revising_report=False):
                return native_agent(role, tools, current, feedback=feedback, paper_id=paper_id,
                    revising=role == "writer" and revising_report)
            graph = build_research_convergence_graph(artifacts=artifacts, question=state["question"], feedback=state["feedback"],
                hierarchical=True, max_correction_rounds=2,
                run_author=run_author, review_revisions=review_revisions,
                make_agent=make_agent, max_parallel_authors=profile["max_parallel_tasks"],
                research_review_context={**{r: state.get("case_review", {})[r]["review"] for r in ("counter", "verifier") if r in state.get("case_review", {})},
                    "lead_handoff": state.get("research_handoff"),
                    "incomplete_review_records": {r: {k: state['case_review'][r].get(k) for k in ('status', 'recorded_findings', 'incomplete_output')}
                        for r in ('counter', 'verifier') if state.get('case_review', {}).get(r, {}).get('status') not in (None, 'review_submitted')}}, existing_state=existing,
                execution_plan=(state.get("research_handoff") or {}).get("execution_plan"),
                human_feedback=existing.get("message") if existing else None).compile()
            return await graph.ainvoke({}, config)

    async def converge(state, config: RunnableConfig):
        return await execute_convergence(state, config)

    async def revise_research(state, config: RunnableConfig):
        return await execute_convergence({**state, "feedback": {}}, config, existing=state)

    def interactive(role):
        async def execute(state, config: RunnableConfig):
            guidance = await read_guidance() if read_guidance else []
            if guidance:
                state = {**state, 'messages': [*state.get('messages', []), HumanMessage(content=
                    '\n'.join(row['message'] for row in guidance))]}
            async with tools_for(state) as (artifacts, tools):
                if execution.mode in {"auto", "selected", "standard"}:
                    allowed = [b for b in case["branch_topics"] if not execution.branch_ids or b["branch_id"] in execution.branch_ids]
                    research_tools = tools
                    @tool(response_format="content_and_artifact")
                    async def consult_research_specialist(branch_id: str, objective: str, runtime: ToolRuntime):
                        """Ask one independent research specialist a focused subquestion. Choose an allowed branch from the supplied scope. Child returns source-bound findings, never private messages. Use only when another perspective is necessary."""
                        if branch_id not in {b["branch_id"] for b in allowed} or not 10 <= len(objective) <= 4000:
                            raise ToolException("请选择已允许的方向，并提供10–4000字符的具体研究问题")
                        task_id = runtime.tool_call_id
                        emit({"kind": "task", "actor": branch_id, "task_id": task_id, "event": "started", "status": "running", "objective": objective})
                        # Reuse native create_agent, run config and checkpoints. The child has
                        # its own short history and no delegation tool, so no recursive fan-out.
                        child = native_agent("quick_writer", research_tools, artifacts, interactive=True, actor_override=branch_id)
                        output = await child.ainvoke({"messages": [HumanMessage(content=json.dumps({
                            "research_question": objective, "scope": next(b for b in allowed if b["branch_id"] == branch_id),
                            "research_as_of": artifacts.research_as_of, "catalog": artifacts.catalog(),
                            "instruction": "核对所分配问题，必要时读当前资料，给出有来源的简短答复。"}, ensure_ascii=False))],
                            "report": state.get("report", {}), "revisions": state.get("revisions", {}),
                            "human_edits": state.get('human_edits', []), "conversation": [], "request_action": "ask"}, runtime.config)
                        result = output.get("output", {})
                        if result.get("kind") != "answer" or not result.get("citations"):
                            raise ToolException("专家没有提交有效的来源绑定回答；不能推定完成")
                        emit({"kind": "task", "actor": branch_id, "task_id": task_id, "event": "outcome", "status": "submitted", "objective": objective})
                        return json.dumps({"answer": result["answer_markdown"], "source_ids": list(result["citations"]), "notice": "专家结论仍需主研究者核对"}, ensure_ascii=False), {"citations": result["citations"]}
                    tools = [*tools, consult_research_specialist]
                    state = {**state, "messages": [*state.get("messages", []), HumanMessage(content=
                        "本次允许按需要调用 consult_research_specialist，请自行判断是否必要，不为填满名单而分派。每次聚焦一个子问题；专家只收到该问题和可回读资料。允许的方向：" + json.dumps(allowed, ensure_ascii=False))]}
                agent = native_agent(role, tools, artifacts, interactive=True)
                return await agent.ainvoke({key: value for key, value in state.items() if key != "case_papers"}, config)
        return RunnableLambda(execute)

    def guarded(name, function):
        async def invoke(state, config: RunnableConfig):
            try:
                return await function(state, config)
            except asyncio.CancelledError:
                cancelled.set()
                raise
            except Exception as exc:
                import re
                # Publish domain error codes, never arbitrary provider payloads,
                # credentials, SQL, file paths or nested private agent messages.
                code = str(exc) if re.fullmatch(r"[a-z][a-z0-9_:]{0,180}", str(exc)) else type(exc).__name__
                emit({"kind": "stage", "actor": name, "event": "failure", "status": "error",
                    "error_type": type(exc).__name__, "objective": f"本阶段未完成。系统记录：{code}。已产生的候选输出和执行记录保留；这不是模型对失败原因的解释。"})
                raise
        return RunnableLambda(invoke)

    return {"hierarchical": True, "research": guarded("research", research), "review": guarded("review", review), "triage_review": guarded("lead_review_triage", triage_review), "converge": guarded("convergence", converge),
            "revise_research": guarded("research_revision", revise_research), "writer": interactive("writer"),
            "verifier": interactive("report_verifier"), "quick_writer": interactive("quick_writer")}


@asynccontextmanager
async def research_session_graph(config: RunnableConfig, runtime: ServerRuntime):
    if runtime.execution_runtime is None:
        def unavailable(_):
            raise RuntimeError("schema_only_execution_unavailable")
        phases = {key: RunnableLambda(unavailable) for key in ("research", "review", "converge", "writer", "verifier", "quick_writer", "revise_research")}
        yield build_research_session_graph(**phases).compile(name="research_session")
        return
    from .agent_server_entry import _require_langsmith_execution_environment
    _require_langsmith_execution_environment(config)
    if os.environ.get("FINSIGHT_RESEARCH_SESSION_ENABLED") != "1":
        raise ValueError("fresh_research_deployment_not_enabled")
    ids = config["configurable"]
    thread_id, run_id = str(UUID(str(ids["thread_id"]))), str(UUID(str(ids["run_id"])))
    root = Path(os.environ["FIN_REPO_ROOT"])
    settings = json.loads(Path(os.environ["FINSIGHT_REPORT_SESSION_SETTINGS"]).read_text(encoding="utf-8"))
    profile, case = load_research_runtime_profile(root)
    studio = configuration_from_native(config)
    public, private = session_audit_sinks(Path(settings["audit_root"]) / thread_id / run_id)
    execution = execution_from_config(config).validate_catalog(case["branch_topics"])
    public({"kind": "stage", "actor": "research_configuration", "event": "applied", "status": "loaded",
        "objective": "本次运行已固定：" + {"auto": "自由调度", "selected": "指定专家", "single": "单 Agent", "standard": "完整研究"}[execution.mode]
            + "；模型：" + ("按角色配置" if execution.model == "default" else execution.model)
            + ("；所选方向：" + "、".join(b["objective"] for b in case["branch_topics"] if b["branch_id"] in execution.branch_ids) if execution.branch_ids else ""),
        "recorded_at": datetime.now(timezone.utc).isoformat(), "run_id": run_id})
    if studio:
        public({"kind": "stage", "actor": "research_configuration", "event": "applied", "status": "loaded",
            "objective": f"已固定配置：{studio.title} · {studio.digest[:12]} · 专家并行 {studio.max_parallel_tasks} · 审查 {studio.review_order}",
            "recorded_at": datetime.now(timezone.utc).isoformat(), "run_id": run_id})
    from langgraph_sdk import get_client
    asset_view = None
    if os.environ.get('FINSIGHT_TASK_ATTACHMENTS_ROOT'):
        from sec_agent.research_foundation.task_asset_updates import TaskAssetUpdates, TaskAssetView, asset_update_prompt
        updates = TaskAssetUpdates(os.environ['FINSIGHT_TASK_ATTACHMENTS_ROOT'])
        updates.pin(thread_id, run_id, ids.get('finsight_asset_revision', 0))
        asset_view = TaskAssetView(updates.store.root, thread_id, run_id)
        if asset_view.binding:
            public({'kind': 'stage', 'actor': 'asset_inputs', 'event': 'applied', 'status': 'requires_reassessment',
                'objective': f"本次运行采用资料输入 r{asset_view.binding['revision']}；已有研究结果仍须核查影响，未自动更新。",
                'recorded_at': datetime.now(timezone.utc).isoformat(), 'run_id': run_id})
    native = get_client()  # official in-process Agent Server connection
    async def read_guidance():
        thread = await native.threads.get(thread_id)
        from .user_context import user_context_prompt
        metadata = thread.get('metadata', {})
        current = user_context_prompt(metadata.get('owner_id','local-pilot'),thread_id)
        from sec_agent.research_foundation.asset_workspace import asset_context_prompt
        assets = asset_update_prompt(asset_view) if asset_view and asset_view.binding else asset_context_prompt(metadata)
        return [*([{'message':assets}] if assets else []), *metadata.get("research_guidance", []), *([{'message':current}] if current else [])]
    try:
        from .research_budget import budget_from_host
        thread = await native.threads.get(thread_id)
        budget_scope = await asyncio.to_thread(budget_from_host, settings, thread_id=thread_id,
            metadata=thread.get('metadata', {}), environment=os.environ)
        phases = create_research_phase_runnables(root=root, settings=settings, profile=profile, case=case,
            thread_id=thread_id, run_id=run_id, api_key=SecretStr(os.environ["DEEPSEEK_API_KEY"]), public_sink=public,
            private_sink=private, read_guidance=read_guidance, studio=studio, execution=execution,
            blocked_model_inputs=tuple(ids.get('finsight_blocked_model_inputs', ())),
            plan_invocation_id=ids.get('finsight_plan_invocation_id'), budget_scope=budget_scope,
            environment={**os.environ, **({'FINSIGHT_RESEARCH_AS_OF': ids['finsight_research_as_of']}
                if ids.get('finsight_research_as_of') else {})})
        from .working_memory_tools import native_memory_scope
        thread = await native.threads.get(thread_id)
        with native_memory_scope(thread.get('metadata', {}).get('owner_id', 'local-pilot'), thread_id):
            yield build_research_session_graph(**phases).compile(name="research_session").with_config({"recursion_limit": 280})
    except Exception as exc:
        from langgraph.errors import GraphInterrupt
        if not isinstance(exc, GraphInterrupt):
            import re
            code = str(exc).split(":", 1)[0]
            code = code if re.fullmatch(r"[a-z_]{3,96}", code) else type(exc).__name__
            # Persist parent/handoff errors too, so starting a later native run
            # does not erase the previous attempt's public failure explanation.
            public({"kind": "stage", "actor": "research", "event": "failure", "status": "error",
                "error_type": type(exc).__name__, "objective": f"运行未完成。系统错误代码：{code}。已产生的候选输出与执行记录保留；这不是模型对失败原因的解释。",
                "recorded_at": datetime.now(timezone.utc).isoformat(), "run_id": run_id})
        raise
    finally:
        await native.http.client.aclose()
