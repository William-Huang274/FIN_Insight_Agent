"""Java-admitted organization task -> ACP -> existing financial tools.

An explicit host binding selects this qualified execution path. It never falls
back to the old model loop. Native Agent Server still owns the public run,
checkpoint and cancel endpoint; the fixed upstream process owns conversation.
"""
import asyncio
from contextlib import asynccontextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets

from acp.schema import HttpMcpServer, HttpHeader
from langchain_core.messages import AIMessage, ToolMessage, convert_to_messages, messages_from_dict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .conversation_agent import GrantedTool, research_system_prompt
from .conversation_tools import conversation_tools
from .harness_acp_session import admitted_acp_session, completed_recovery, _persist
from .harness_business_tools import HarnessBusinessTools
from .harness_dispatch_host import HarnessDispatchHost
from .harness_provider_transport import HarnessProviderTransport
from .harness_local_services import harness_local_services
from .harness_profile import profile_overlay
from .on_demand_research import OnDemandResearchState
from .organization_work_session import organization_source_tool, observed_source_tool, validate_work_input, artifact_reader
from .research_graph_contracts import canonical_sha256
from .working_memory_tools import native_memory_scope, working_memory_tools


def native_messages(rows):
    return [messages_from_dict([{'type': m['type'], 'data': m}])[0]
            if isinstance(m, dict) and m.get('type') in {'human', 'ai', 'system', 'tool', 'function', 'chat'}
            else convert_to_messages([m])[0] if isinstance(m, dict) else m for m in rows]


@asynccontextmanager
async def organization_harness_session(*, native, resources, authority, check, organization,
        phase_arguments, config, grant, expected_input, environment):
    """No browser-controlled paths, model identity, source authority or money."""
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    tid, rid = phase_arguments['thread_id'], phase_arguments['run_id']
    options = phase_arguments['settings']['harness_execution_bindings'][tid]
    if options['manifest_digest'] != grant['manifest_digest']:
        raise ValueError('harness_deployment_manifest_mismatch')
    execution = phase_arguments['execution']
    selected = execution.apply_profile(phase_arguments['profile'])['nodes']['lead']['profile']
    if options['model'] != selected['model'] or options['reasoning'] != selected['reasoning_effort']:
        raise ValueError('harness_admitted_model_configuration_mismatch')
    budget = phase_arguments['budget_scope']
    if budget is None or options['model'] not in budget.prices:
        raise ValueError('harness_shared_task_budget_required')
    checkpoint = grant.get('report_action_request', {}).get('checkpoint_id')
    admitted = (await native.threads.get_state(tid, **({'checkpoint_id': checkpoint} if checkpoint else {}))).get('values') or {}
    admitted = {**admitted, 'messages': native_messages(admitted.get('messages', []))}
    binary = Path(options['binary']).resolve(strict=True)
    # Check the small pinned executable at launch, not every library object.
    if sha256(binary.read_bytes()).hexdigest() != options['binary_sha256']:
        raise ValueError('harness_executable_release_mismatch')
    directory = Path(environment['FINSIGHT_HARNESS_STATE_ROOT']).resolve() / tid
    directory.mkdir(parents=True, exist_ok=True)
    run_directory = directory / rid
    run_directory.mkdir(exist_ok=True)
    owner = 'organization:' + grant['organization_id']
    navigation = (organization.retrieval.navigation() if organization.retrieval else
                  OrganizationSourceNavigation(organization.reader, workbench_url=organization.workbench_url))
    # Keep the existing paged receipt directory, not its old automatic
    # orientation/summary middleware. Recovery discovers saved effects here.
    grants = [g for g in conversation_tools(thread_id=tid)
              if g.tool.name in {'browse_context', 'read_context_turn', 'read_saved_result',
                                 'get_research_method', 'calculate_research_metric', 'create_report_chart'}]
    grants.append(GrantedTool(organization_source_tool(navigation, check), 'read', '当前组织任务的固定来源'))
    grants.extend(GrantedTool(t, 'working_note_write' if t.name == 'WriteWorkingNote' else 'read',
                  '当前组织任务的版本化工作笔记') for t in working_memory_tools('research_partner', owner=owner, workspace=tid))
    if checkpoint:
        from .conversation_handoff import handoff_tools
        grants.extend(handoff_tools(reference={'source_thread': tid, 'checkpoint_id': checkpoint},
            sdk=native, owner_id=owner, access_check=check))
    from .working_memory import WorkingMemory
    from .harness_artifact_tools import artifact_tools
    memory = WorkingMemory(environment['FINSIGHT_WORKING_MEMORY_PATH'], owner=owner, workspace=tid,
                           actor='research_partner', access_check=check, allow_remote_search=False)
    intent = grant.get('report_action_request', {}).get('delivery_intent', execution.delivery_intent)
    require_review = grant.get('report_action_request', {}).get('require_report_review', execution.require_report_review)
    if require_review:
        raise ValueError('harness_independent_review_not_yet_qualified')
    def artifacts(state):
        with organization(run_invocation_id='harness:' + rid, source_read_enabled=True) as data:
            return artifact_reader(data, navigation, state)
    grants.append(observed_source_tool(artifacts, check))
    grants.extend(artifact_tools(artifacts=artifacts, memory=memory, delivery_intent=intent, require_review=require_review))
    scope = lambda: native_memory_scope(owner, tid, access_check=check, allow_remote_search=False)
    async with AsyncSqliteSaver.from_conn_string(str(directory / 'business-checkpoint.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id=tid, check=check, scope=scope)
        await bridge.initialize({**admitted, 'question': grant['question']})
        def active_authority():
            bridge.access()
            return authority()
        token = secrets.token_urlsafe(32)
        role = budget.roles['lead']
        dispatch = HarnessDispatchHost(store=budget.store, owner=budget.owner, budget=budget.budget,
            execution_id=tid, run_id=rid, manifest_digest=grant['manifest_digest'], authority=active_authority,
            prices=budget.prices[options['model']], provider=options['provider'], basis=options['token_budget_basis'],
            reservation_micros=role['reservation_micros'], reservation_basis=role['reservation_basis'],
            receipts=run_directory / 'wire', wire_usage=lambda _: None, public_sink=phase_arguments['public_sink'])
        key = environment[options['provider_key_env']]
        transport = HarnessProviderTransport(dispatch, protocol=options['protocol'], endpoint=options['provider_endpoint'],
            provider_headers={'Authorization': 'Bearer ' + key}, token=token)
        dispatch.wire_usage = transport.meter

        async def guard(state):
            return validate_work_input(state, check=check, grant=grant, admitted_values=admitted, expected_input=expected_input)

        async def project(state, result):
            business = await bridge.state()
            from .task_outcome import TaskOutcome
            output = AIMessage(content=result['text'], additional_kwargs={'harness_session_id': result['session_id']})
            # Financial observations stay in the existing export/readback
            # projection. They are not transplanted into native ACP history.
            before = {m.id for m in state.get('messages', []) if m.id}
            receipts = [m for m in business.get('messages', []) if m.id not in before]
            delivery = business.get('delivery')
            submitted = bool(delivery) or (intent == 'answer' and bool(result['text']))
            return {**{k: business[k] for k in ('report', 'report_version', 'delivery') if k in business},
                'messages': [*receipts, output], 'task_outcome': TaskOutcome(task_id=tid, run_id=rid,
                execution_status='submitted' if submitted else 'incomplete', phase='harness_result',
                artifact_status='submitted' if submitted else 'none', artifact_kind=intent if submitted else None,
                artifact_digest=delivery['artifact_digest'] if delivery else canonical_sha256(result['text']),
                author_note_status='missing').model_dump(mode='json')}

        async def work(state):
            binding = {'execution_id': tid, 'manifest_digest': grant['manifest_digest'],
                       'release': options['binary_sha256'], 'model': options['model']}
            action = grant.get('report_action_request', {})
            await bridge.begin_command(grant.get('report_command_id', rid),
                recovering=action.get('action') == 'recover')
            if action.get('action') == 'recover':
                recovered = completed_recovery(directory, previous_run_id=action['previous_run_id'], binding=binding)
                if recovered is not None:
                    _persist(run_directory / 'turn.private.json', {**recovered, 'reused_from_run': action['previous_run_id']})
                    return await project(state, recovered)
            async with harness_local_services(business=bridge, dispatch=dispatch, transport=transport, token=token) as endpoint:
                prompt = research_system_prompt(bridge.tools, 'Research as of: ' + organization.research_as_of +
                    '\nRequested delivery: ' + intent + '. Save useful working understanding as needed; only deliver the requested artifact form.')
                patch = profile_overlay(model=options['model'], protocol=options['protocol'], endpoint=endpoint,
                    prompt=prompt, context_window=options['context_window'], output_tokens=options['output_tokens'],
                    summary_tokens=options['summary_tokens'], reasoning=options['reasoning'],
                    dispatch_plugin=phase_arguments['root'] / 'integrations/deepseek-harness/dispatch.mjs')
                patch_path = run_directory / 'profile.patch.json'
                _persist(patch_path, patch)
                child_env = {k: v for k, v in environment.items() if k.upper() in {
                    'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT'}}
                child_env.update(DSH_HOME=str(directory / 'native'), HOME=str(directory), USERPROFILE=str(directory),
                                 FIN_HARNESS_LOCAL_TOKEN=token, NO_PROXY='127.0.0.1,localhost')
                servers = [HttpMcpServer(type='http', name='financial', url=endpoint + '/business/',
                            headers=[HttpHeader(name='Authorization', value='Bearer ' + token)])]
                new_session = not (directory / 'session-binding.json').exists()
                async with admitted_acp_session(binary=str(binary), arguments=['--profile', 'sdk-minimal', '--patch', str(patch_path)],
                        environment=child_env, directory=directory, binding=binding, run_id=rid,
                        authority=active_authority, stop=bridge.stop, mcp_servers=servers) as session:
                    request = state['messages'][-1].content
                    if new_session:
                        # Explicit lineage only: never insert an old summary or
                        # old assistant/tool messages into the new native log.
                        receipts = [m for m in admitted.get('messages', []) if isinstance(m, ToolMessage)]
                        request = json.dumps({'original_question': grant['question'], 'current_command': request,
                            'handoff': {'kind': 'imported_fin_tool_records_not_native_acp_history', 'checkpoint_id': checkpoint,
                                'successful_receipts': [{'tool_call_id': m.tool_call_id, 'tool': m.name}
                                                       for m in receipts if m.status == 'success'],
                                'readback': 'read_saved_result; ReadWorkingNote/SearchWorkingNotes for saved understanding'}}, ensure_ascii=False)
                    result = await session.prompt(request)
                    if result['status'] != 'completed':
                        raise RuntimeError('harness_prompt_not_completed:' + result['stop_reason'])
                    return await project(state, result)
        graph = StateGraph(OnDemandResearchState)
        graph.add_node('admitted_input', guard)
        graph.add_node('work', work)
        graph.add_edge(START, 'admitted_input')
        graph.add_edge('admitted_input', 'work')
        graph.add_edge('work', END)
        yield graph.compile(name='research_session')
