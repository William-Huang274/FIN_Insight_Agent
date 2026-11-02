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
from .conversation_tools import conversation_tools, SAVED_RESULT_TOOLS
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


def receipt_replay_identity(directory, tid, import_digest, clean_import, replay_id=None):
    """Host-only branch identity; repeat experiments never reuse later notes.

    No ID preserves the original deployment layout and normal recovery path.
    A branch still imports the exact pinned receipts, not edited model history.
    """
    from uuid import UUID, uuid5, NAMESPACE_URL
    session = directory / ('import-' + import_digest) if import_digest else directory
    identity = tid + ':' + str(import_digest)
    if replay_id is not None:
        if not clean_import or not import_digest:
            raise ValueError('harness_replay_id_requires_isolated_import')
        replay_id = str(UUID(replay_id))
        session = session / ('replay-' + replay_id)
        identity += ':' + replay_id
    workspace = str(uuid5(NAMESPACE_URL, identity)) if clean_import else tid
    return session, workspace, session if clean_import else directory


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
    # A host-declared legacy import starts a distinct native ACP lineage. The
    # old failed ACP attempt remains untouched; its empty handoff/error history
    # must not become the starting history for the corrected migration.
    import_digest = options.get('legacy_receipt_import', {}).get('sha256')
    if import_digest is not None and (len(import_digest) != 64 or any(c not in '0123456789abcdef' for c in import_digest)):
        raise ValueError('harness_legacy_import_digest_invalid')
    # Explicit operator replay starts before a faulty generation. Keep original
    # ledgers/notes intact, and do not seed this branch from a later outer answer.
    # This is a receipt handoff, not a fabricated native conversation fork.
    clean_import = options.get('isolated_receipt_replay', False)
    if clean_import and not import_digest:
        raise ValueError('harness_isolated_replay_requires_pinned_checkpoint')
    session_directory, memory_workspace, business_directory = receipt_replay_identity(
        directory, tid, import_digest, clean_import, options.get('receipt_replay_id'))
    business_directory.mkdir(parents=True, exist_ok=True)
    run_directory = directory / rid
    run_directory.mkdir(exist_ok=True)
    owner = 'organization:' + grant['organization_id']
    # Prepare the fixed release before the first paid turn. Otherwise the
    # first MCP search spends its request deadline loading cached proofs even
    # though no new original needs verification. The maintained lifecycle owns
    # reuse; do not introduce a second warm-up/cache implementation here.
    if organization.retrieval is not None:
        await asyncio.to_thread(organization.prepare_retrieval)
    navigation = (organization.retrieval.navigation() if organization.retrieval else
                  OrganizationSourceNavigation(organization.reader, workbench_url=organization.workbench_url))
    # Keep the existing paged receipt directory, not its old automatic
    # orientation/summary middleware. Recovery discovers saved effects here.
    grants = [g for g in conversation_tools(thread_id=tid)
              if g.tool.name in {'browse_context', 'read_context_turn', 'read_saved_result',
                                 'get_research_method', 'calculate_research_metric', 'create_report_chart'}]
    public_web = options.get('allow_public_web', False)
    grants.append(GrantedTool(organization_source_tool(navigation, check, public_web=public_web), 'read', '当前组织任务的固定来源'))
    if public_web:
        from .conversation_web import public_web_tool
        grants.append(public_web_tool(thread_id=tid, run_id=rid,
            method_digest=sha256(research_system_prompt(['read_public_source', 'get_research_method']).encode('utf-8')).hexdigest(),
            cache_root=directory / 'public-source-cache', research_as_of=organization.research_as_of))
    grants.extend(GrantedTool(t, 'working_note_write' if t.name == 'WriteWorkingNote' else 'read',
                  '当前组织任务的版本化工作笔记') for t in working_memory_tools('research_partner', owner=owner, workspace=memory_workspace))
    # The business receipt store is the single historical readback surface.
    # Exposing a second SDK handoff to the outer checkpoint would advertise an
    # empty source list when the old research lived in a nested graph.
    from .working_memory import WorkingMemory
    from .harness_artifact_tools import artifact_tools
    memory = WorkingMemory(environment['FINSIGHT_WORKING_MEMORY_PATH'], owner=owner, workspace=memory_workspace,
                           actor='research_partner', access_check=check, allow_remote_search=False)
    intent = grant.get('report_action_request', {}).get('delivery_intent', execution.delivery_intent)
    require_review = grant.get('report_action_request', {}).get('require_report_review', execution.require_report_review)
    if require_review:
        raise ValueError('harness_independent_review_not_yet_qualified')
    def artifacts(state, **kwargs):
        with organization(run_invocation_id='harness:' + rid, source_read_enabled=True,
                          memory_workspace=memory_workspace) as data:
            return artifact_reader(data, navigation, state, allow_public_sources=public_web, **kwargs)
    grants.append(observed_source_tool(artifacts, check))
    grants.extend(artifact_tools(artifacts=artifacts, memory=memory, delivery_intent=intent, require_review=require_review))
    scope = lambda: native_memory_scope(owner, memory_workspace, access_check=check, allow_remote_search=False)
    async with AsyncSqliteSaver.from_conn_string(str(business_directory / 'business-checkpoint.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id=tid, check=check, scope=scope)
        recovery_receipt = await bridge.initialize({**({} if clean_import else admitted), 'question': grant['question']},
            recovering=grant.get('report_action_request', {}).get('action') == 'recover')
        if recovery_receipt:
            _persist(run_directory / 'tool-recovery.json', recovery_receipt)
        if options.get('legacy_receipt_import'):
            from .harness_legacy_import import legacy_receipts
            await asyncio.to_thread(check)
            imported = await asyncio.to_thread(legacy_receipts, options['legacy_receipt_import'], grant=grant)
            await bridge.import_receipts(imported)
        def active_authority():
            bridge.access()
            return authority()
        def dispatch_authority():
            bridge.model_access()
            return authority()
        token = secrets.token_urlsafe(32)
        role = budget.roles['lead']
        dispatch = HarnessDispatchHost(store=budget.store, owner=budget.owner, budget=budget.budget,
            execution_id=tid, run_id=rid, manifest_digest=grant['manifest_digest'], authority=dispatch_authority,
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
            from .source_references import render_answer_references
            text, citations, unresolved = render_answer_references(result['text'], business)
            output = AIMessage(content=text, additional_kwargs={'harness_session_id': result['session_id'],
                'citation_bindings': citations, 'unresolved_citations': unresolved})
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
                recovered = completed_recovery(session_directory, previous_run_id=action['previous_run_id'], binding=binding)
                if recovered is not None:
                    _persist(run_directory / 'turn.private.json', {**recovered, 'reused_from_run': action['previous_run_id']})
                    return await project(state, recovered)
            async with harness_local_services(business=bridge, dispatch=dispatch, transport=transport, token=token) as endpoint:
                prompt = research_system_prompt(bridge.tools, 'Research as of: ' + organization.research_as_of +
                    '\nRequested delivery: ' + intent + '. Save useful working understanding as needed; only deliver the requested artifact form.'+
                    '\nUse returned citation_handle values in source_id fields and [REF-...] citations. They bind exact observed originals/calculations; do not shorten them further. Original long IDs remain compatible.')
                patch = profile_overlay(model=options['model'], protocol=options['protocol'], endpoint=endpoint,
                    prompt=prompt, context_window=options['context_window'], output_tokens=options['output_tokens'],
                    summary_tokens=options['summary_tokens'], reasoning=options['reasoning'],
                    dispatch_plugin=phase_arguments['root'] / 'integrations/deepseek-harness/dispatch.mjs')
                patch_path = run_directory / 'profile.patch.json'
                _persist(patch_path, patch)
                child_env = {k: v for k, v in environment.items() if k.upper() in {
                    'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT'}}
                child_env.update(DSH_HOME=str(session_directory / 'native'), HOME=str(session_directory), USERPROFILE=str(session_directory),
                                 FIN_HARNESS_LOCAL_TOKEN=token, NO_PROXY='127.0.0.1,localhost')
                servers = [HttpMcpServer(type='http', name='financial', url=endpoint + '/business/',
                            headers=[HttpHeader(name='Authorization', value='Bearer ' + token)])]
                new_session = not (session_directory / 'session-binding.json').exists()
                async with admitted_acp_session(binary=str(binary), arguments=['--profile', 'sdk-minimal', '--patch', str(patch_path)],
                        environment=child_env, directory=session_directory, binding=binding, run_id=rid,
                        authority=active_authority, stop=bridge.stop, mcp_servers=servers) as session:
                    request = state['messages'][-1].content
                    if recovery_receipt:
                        request = json.dumps({'current_command': request,
                            'runtime_recovery': recovery_receipt}, ensure_ascii=False)
                    if new_session:
                        # Explicit lineage only: never insert an old summary or
                        # old assistant/tool messages into the new native log.
                        receipts = [m for m in (await bridge.state()).get('messages', []) if isinstance(m, ToolMessage)]
                        request = json.dumps({'original_question': grant['question'], 'current_command': request,
                            'handoff': {'kind': 'imported_fin_tool_records_not_native_acp_history', 'checkpoint_id': checkpoint,
                                'source_checkpoint': options.get('legacy_receipt_import', {}).get('source_checkpoint'),
                                'successful_receipts': [{'tool_call_id': m.tool_call_id, 'tool': m.name}
                                                       for m in receipts if m.status == 'success' and m.name in SAVED_RESULT_TOOLS],
                                'readback': 'browse_context for saved receipt keys; read_saved_result for exact contents; ReadWorkingNote/SearchWorkingNotes for saved understanding'}}, ensure_ascii=False)
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
