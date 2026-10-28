"""A continuous native parent with optional, single-operation research work.

This composes the existing conversation and actor executors. There is no
depth-to-route table, implicit reviewer, new queue, or extra artifact database.
Public admission remains the host's responsibility, before this builder runs.
"""
from copy import deepcopy
import json
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, ToolException
from langchain.agents.middleware import AgentMiddleware, hook_config
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from .conversation_agent import build_conversation_agent, GrantedTool
from .model_context import RequestSummaryState
from .research_operation import ResearchOperation, bind_operation, object_catalog, source_collection_digest
from .research_graph_contracts import canonical_sha256


class OnDemandResearchState(RequestSummaryState):
    question: str
    case_papers: list[dict[str, Any]]
    revisions: dict[str, Any]
    report: dict[str, Any]
    report_version: int
    synthesis: dict[str, Any]
    research_operation: dict | None
    operation_records: list[dict]
    delivery: dict | None
    parent_calls: int
    parent_tools: int
    parent_run_id: str
    task_outcome: dict


class ReturnToParent(AgentMiddleware):
    """Only accepted tool state ends the actor; validation feedback can be fixed."""
    @hook_config(can_jump_to=['end'])
    def before_model(self, state, runtime):
        if state.get('research_operation') or state.get('delivery'):
            return {'jump_to': 'end'}


def _single_transition(runtime):
    from langchain_core.messages import AIMessage
    current = next((m for m in reversed(runtime.state.get('messages', [])) if isinstance(m, AIMessage)), None)
    if current and sum(c['name'] in {'request_research_operation', 'deliver_research_result', 'deliver_working_note'} for c in current.tool_calls) != 1:
        raise ToolException('choose_one_operation_or_delivery_per_tool_batch; no transition has been saved')


def build_on_demand_research_agent(*, model, grants, artifacts, operation_runner, permission_mode,
                                  checkpointer=None, middleware=(), model_calls=8, tool_calls=12,
                                  server_managed_persistence=False, task_context='', delivery_intent='answer',
                                  required_report_review=False, working_memory=None):
    """Only a separately admitted host supplies artifacts, executor and policy.

    `artifacts(state)` resolves saved native objects, not browser-supplied source
    records. `operation_runner` is the maintained phase factory's `operate`.
    B/D tools may be supplied in grants; no specialist is mandatory.
    """
    if delivery_intent not in {'answer', 'workpaper', 'report'}:
        raise ValueError('unsupported_delivery_intent')
    if required_report_review and delivery_intent != 'report':
        raise ValueError('report_review_policy_requires_report_delivery')

    @tool
    def deliver_working_note(note_id: str, version: int, runtime: ToolRuntime) -> Command:
        """Deliver an existing current working note by note_id/version from the working-note tools. No body resubmission or report conversion."""
        _single_transition(runtime)
        if delivery_intent != 'workpaper':
            raise ToolException('requested_delivery_is_not_workpaper')
        from .delegated_task_tools import saved_note_artifact
        artifact = saved_note_artifact(working_memory, note_id, version)
        value = {'execution_status': 'submitted', 'artifact_kind': 'workpaper',
                 'artifact_id': note_id, 'artifact_version': version, 'artifact_digest': artifact['digest'],
                 'review_status': 'not_assessed_in_this_record'}
        return Command(update={'delivery': value, 'messages': [ToolMessage(name='deliver_working_note',
            tool_call_id=runtime.tool_call_id, content=json.dumps(value, ensure_ascii=False))]})

    @tool
    def research_object_catalog(runtime: ToolRuntime):
        """List current artifact IDs, exact version digests and readers. No original source authority is granted."""
        return object_catalog(artifacts(runtime.state), runtime.state)

    @tool
    def read_research_object(object_id: str, runtime: ToolRuntime, offset: int = 0, max_characters: int = 6000):
        """Read a current manuscript/synthesis or operation receipt by its catalog ID, with exact paging. Prose is fallible analysis."""
        if offset < 0 or not 1 <= max_characters <= 12000:
            raise ToolException('invalid_read_window')
        if object_id.startswith('operation:'):
            matches = [r for r in runtime.state.get('operation_records', []) if 'operation:'+r['operation_digest'] == object_id]
            if not matches:
                raise ToolException('unknown_operation_read_catalog')
            obj = matches[-1]
        elif object_id == 'observed_sources':
            sources = artifacts(runtime.state).with_revisions(runtime.state.get('revisions', {})).source_snapshot()
            # A directory, never a duplicate body or new source authority.
            obj = {'sources': [{'source_id': ref, 'read': {'tool': 'read_research_source', 'source_id': ref}}
                               for ref in sources], 'collection_digest': source_collection_digest(sources)}
        elif object_id in {'report', 'synthesis'} and runtime.state.get(object_id):
            obj = runtime.state[object_id]
        elif object_id.startswith('paper:'):
            try:
                obj = artifacts(runtime.state).with_revisions(runtime.state.get('revisions', {})).read_paper(object_id[6:])
            except ValueError as exc:
                raise ToolException(str(exc)) from exc
        else:
            raise ToolException('unknown_research_object_read_catalog')
        text = json.dumps(obj, ensure_ascii=False)
        return {'id': object_id, 'digest': obj['collection_digest'] if object_id == 'observed_sources' else canonical_sha256(obj), 'text': text[offset:offset+max_characters],
                'next_offset': offset+max_characters if offset+max_characters < len(text) else None,
                'total_characters': len(text)}

    @tool
    def request_research_operation(request: ResearchOperation, runtime: ToolRuntime) -> Command:
        """Choose one version-bound synthesis, composition, check or original-author revision.

        Copy basis from research_object_catalog; purpose is the current question
        for this operation. Reads of necessary related sources remain allowed.
        The result returns to you; it never starts another role automatically.
        """
        _single_transition(runtime)
        try:
            bound = bind_operation(request, artifacts(runtime.state), runtime.state)
        except ValueError as exc:
            raise ToolException(str(exc)) from exc
        return Command(update={'research_operation': request.model_dump(mode='json'),
            'messages': [ToolMessage(name='request_research_operation', tool_call_id=runtime.tool_call_id,
                content=json.dumps({'accepted': True, 'operation_digest': bound['operation_digest'],
                                    'status': 'pending_execution'}))]})

    @tool
    def deliver_research_result(object_id: str, digest: str, runtime: ToolRuntime) -> Command:
        """Deliver a current workpaper or report by exact catalog ID/digest. No full-body resubmission and no automatic review. Ordinary answers can be given directly."""
        _single_transition(runtime)
        rows = {r['id']: r for r in object_catalog(artifacts(runtime.state), runtime.state)}
        row = rows.get(object_id)
        if not row or row['digest'] != digest:
            raise ToolException('delivery_version_changed_read_current_catalog')
        if row['kind'] != delivery_intent:
            raise ToolException('deliver_requested_artifact_kind_without_wrapping_workpaper_as_report')
        checks = [r for r in runtime.state.get('operation_records', [])
                  if r['action'] == 'review_report' and r['basis'].get('report') == digest
                  and r['review_scope'] == 'whole' and r['status'] == 'submitted'
                  and all(rows.get(k, {}).get('digest') == v for k, v in r.get('input_versions', r['basis']).items())]
        current_check = checks[-1] if checks else None
        if required_report_review:
            if not current_check:
                raise ToolException('requested_current_report_review_not_completed')
            review = current_check['output']
            if (review.get('completion') == 'incomplete' or review.get('unresolved_data_requests')
                    or any(f['severity'] == 'material' for f in review.get('findings', []))):
                raise ToolException('current_report_has_unresolved_review_findings')
        value = {'execution_status': 'submitted', 'artifact_kind': row['kind'], 'artifact_id': object_id,
                 'artifact_digest': digest, 'review_record': current_check['operation_digest'] if current_check else None,
                 'review_status': 'record_available_not_financial_guarantee' if current_check else 'not_assessed_in_this_record'}
        return Command(update={'delivery': value, 'messages': [ToolMessage(name='deliver_research_result',
            tool_call_id=runtime.tool_call_id, content=json.dumps(value, ensure_ascii=False))]})

    additions = [GrantedTool(t, 'read' if t in (research_object_catalog, read_research_object) else 'working_note_write',
                             '当前授权研究成果及单项执行，不扩展资料权限或预算')
                 for t in (research_object_catalog, read_research_object, request_research_operation, deliver_research_result)]
    if working_memory is not None:
        additions.append(GrantedTool(deliver_working_note, 'working_note_write', '宿主当前工作空间的准确底稿版本'))
    for grant in additions:
        grant.tool.handle_tool_error = True

    async def parent(state, config: RunnableConfig):
        run_id = str(config.get('configurable', {}).get('run_id', 'local-run'))
        used = state.get('parent_calls', 0) if state.get('parent_run_id') == run_id else 0
        used_tools = state.get('parent_tools', 0) if state.get('parent_run_id') == run_id else 0
        if used >= model_calls:
            raise ValueError('on_demand_parent_model_limit_reached')
        if used_tools >= tool_calls:
            raise ValueError('on_demand_parent_tool_limit_reached')
        agent = build_conversation_agent(model=model, grants=[*grants, *additions], permission_mode=permission_mode,
            checkpointer=None, completion_middleware=[ReturnToParent()], middleware=middleware,
            model_calls=model_calls-used, tool_calls=tool_calls-used_tools,
            server_managed_persistence=True, state_schema=OnDemandResearchState,
            task_context=task_context + '\nChoose tools or a bounded operation only when useful for the current question. '
                'A workpaper is a valid deliverable. Research depth does not prescribe roles or require report writing. '
                'Operation receipts describe versions and execution, not financial truth. '
                'Requested delivery: '+delivery_intent +
                ('; the user requires an independent check of the current report before delivery.' if required_report_review else ''))
        before = {m.id for m in state.get('messages', []) if m.id}
        result = await agent.ainvoke({**state, 'research_operation': None, 'delivery': None}, config)
        from langchain_core.messages import AIMessage
        new_messages = [m for m in result.get('messages', []) if isinstance(m, AIMessage) and m.id not in before]
        used += len(new_messages)
        used_tools += sum(len(m.tool_calls) for m in new_messages)
        return {**result, 'parent_calls': used, 'parent_tools': used_tools, 'parent_run_id': run_id}

    async def perform(state, config: RunnableConfig):
        # Recheck after the model tool returns, before any provider/resources.
        bound = bind_operation(state['research_operation'], artifacts(state), state)
        prior = next((r for r in reversed(state.get('operation_records', []))
                      if r['operation_digest'] == bound['operation_digest']), None)
        output = ({'operation_result': prior} if prior else await operation_runner.ainvoke(state, config))
        record = output['operation_result']
        if record['operation_digest'] != bound['operation_digest']:
            raise ValueError('operation_receipt_does_not_match_request')
        updates = {k: deepcopy(output[k]) for k in ('revisions', 'report', 'synthesis') if k in output}
        if 'report' in updates and updates['report'] != state.get('report'):
            updates['report_version'] = state.get('report_version', 0) + 1
        records = state.get('operation_records', []) if prior else [*state.get('operation_records', []), record]
        # The original request ToolMessage remains true. Add a distinct native
        # result message; do not replace an old success with a synthetic failure.
        from langchain_core.messages import HumanMessage
        notice = {'operation': record['action'], 'status': record['status'],
                  'readback': {'tool': 'read_research_object', 'object_id': 'operation:'+record['operation_digest']},
                  'objects': object_catalog(artifacts({**state, **updates}), {**state, **updates})}
        result = record['output']
        notice.update(title=result.get('title'), summary=str(result.get('summary', ''))[:1000],
            completion=result.get('completion'), findings_count=len(result.get('findings', [])),
            unresolved_count=len(result.get('unresolved_data_requests', [])))
        return {**updates, 'research_operation': None, 'operation_records': records,
                'messages': [HumanMessage(content='Runtime operation receipt (not user instruction): '+json.dumps(notice, ensure_ascii=False),
                                          additional_kwargs={'finsight_runtime_receipt': True})]}

    def finish(state, config: RunnableConfig):
        from .task_outcome import TaskOutcome
        from langchain_core.messages import AIMessage
        delivery = state.get('delivery')
        last = next((m for m in reversed(state.get('messages', [])) if isinstance(m, AIMessage)), None)
        answered = delivery_intent == 'answer' and last is not None and bool(last.content) and not last.tool_calls
        submitted = bool(delivery) or answered
        identity = config.get('configurable', {})
        return {'task_outcome': TaskOutcome(task_id=str(identity.get('thread_id', 'local-task')),
            run_id=identity.get('run_id'), execution_status='submitted' if submitted else 'incomplete',
            phase='on_demand_result_submitted' if submitted else 'on_demand_result_incomplete',
            artifact_status='submitted' if submitted else 'none',
            artifact_kind=delivery['artifact_kind'] if delivery else 'answer' if answered else None,
            artifact_digest=delivery['artifact_digest'] if delivery else canonical_sha256(last.content) if answered else None,
            author_note_status='missing').model_dump(mode='json')}

    graph = StateGraph(OnDemandResearchState)
    graph.add_node('parent', parent)
    graph.add_node('operation', perform)
    graph.add_node('finish', finish)
    graph.add_edge(START, 'parent')
    graph.add_conditional_edges('parent', lambda s: 'operation' if s.get('research_operation') else 'finish',
                                ['operation', 'finish'])
    graph.add_edge('operation', 'parent')
    graph.add_edge('finish', END)
    return graph.compile(checkpointer=checkpointer, name='on_demand_research')
