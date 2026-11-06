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
from .checkpoint_objects import business_checkpointer

from .conversation_agent import GrantedTool, research_system_prompt
from .conversation_tools import conversation_tools, SAVED_RESULT_TOOLS
from .harness_acp_session import admitted_acp_session, completed_recovery, _persist
from .harness_business_tools import HarnessBusinessTools
from .harness_dispatch_host import HarnessDispatchHost
from .harness_provider_transport import HarnessProviderTransport
from .harness_local_services import harness_local_services
from .harness_profile import profile_overlay
from .on_demand_research import OnDemandResearchState
from .organization_work_session import (organization_source_tool, observed_source_tool, validate_work_input,
    select_observed_sources, artifact_reader_from_sources)
from .research_graph_contracts import canonical_sha256
from .working_memory_tools import native_memory_scope, working_memory_tools
from sec_agent.research_foundation.research_methods import preloaded_research_methods, section_guidance


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
    method_content = preloaded_research_methods(options.get('preloaded_research_methods', []))
    method_content += section_guidance(options.get('research_method_sections', []),
                                       include_text=options.get('include_method_section_text') is True)
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
    replay_origin_run = options.get('legacy_receipt_import', {}).get('source_checkpoint', {}).get('run_id') if clean_import else None
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
        from .deepseek_web import DeepSeekWeb
        from sec_agent.research_foundation.external_sources import PublicURLGuard
        key = environment.get('DEEPSEEK_API_KEY')
        paid_search = DeepSeekWeb(api_key=key, budget=budget, thread_id=tid, guard=PublicURLGuard()) if key else None
        agent_identity = environment.get('SEC_USER_AGENT')
        if not agent_identity and environment.get('FINSIGHT_SEC_CONTACT_EMAIL'):
            from financial_facts.sec_snapshot import sec_user_agent_from_environment
            agent_identity = sec_user_agent_from_environment(environment)
        identity_file = phase_arguments['settings'].get('sec_web_identity_file')
        if not agent_identity and identity_file:
            agent_identity = Path(identity_file).read_text(encoding='utf8').strip()
        grants.append(public_web_tool(thread_id=tid, run_id=rid, paid_search=paid_search, sec_user_agent=agent_identity,
            method_digest=sha256(research_system_prompt(['read_public_source', 'get_research_method']).encode('utf-8')).hexdigest(),
            cache_root=directory / 'public-source-cache', research_as_of=organization.research_as_of))
        from .market_prices import market_price_tool
        grants.append(market_price_tool(thread_id=tid, cache_root=directory / 'market-observations',
                                       research_as_of=organization.research_as_of))
        from .legislation import legislation_tool
        from sec_agent.research_foundation.congress_api import CongressAPI
        grants.append(legislation_tool(thread_id=tid, cache_root=directory / 'legislation-observations',
            research_as_of=organization.research_as_of,
            api=CongressAPI(key=environment.get('CONGRESS_API_KEY', ''))))
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
        # Selection feedback must not cross a provider context whose teardown
        # can wrap ToolException in ExceptionGroup and hide it as an MCP 500.
        check()
        sources = select_observed_sources(state, **kwargs)
        with organization(run_invocation_id='harness:' + rid, source_read_enabled=True,
                          memory_workspace=memory_workspace) as data:
            return artifact_reader_from_sources(data, navigation, sources, allow_public_sources=public_web)
    grants.append(observed_source_tool(artifacts, check))
    from .quantitative_prose import quantitative_prose_tool, audit_changes, saved_note_wording
    # Use the same native branch and the last delivery, including a pinned fork.
    binding = {'execution_id': tid, 'manifest_digest': grant['manifest_digest'],
               'release': options['binary_sha256'], 'model': options['model']}
    last_delivery = session_directory / 'last-delivered-run.json'
    previous_run = (json.loads(last_delivery.read_text(encoding='utf8'))['run_id'] if last_delivery.exists()
                    else grant.get('report_action_request', {}).get('previous_run_id'))
    prior_turn = completed_recovery(session_directory, previous_run_id=previous_run, binding=binding) if previous_run else None
    prior_answer = prior_turn['text'] if prior_turn else ''
    if prior_turn and last_delivery.exists():
        delivered_version = json.loads(last_delivery.read_text(encoding='utf8')).get('answer_version')
        if delivered_version:
            prior_answer = next((m.content for m in reversed(admitted['messages']) if isinstance(m, AIMessage)
                and isinstance(m.content, str) and canonical_sha256(m.content) == delivered_version), '')
    prior_review = next((m.additional_kwargs.get('answer_review') for m in reversed(admitted['messages'])
                         if isinstance(m, AIMessage) and m.content == prior_answer), None)
    review_context = (prior_answer, prior_review['opinion']) if prior_review and prior_review.get('opinion') else None
    grants.append(quantitative_prose_tool(prior_answer, lambda: review_context))
    grants.extend(artifact_tools(artifacts=artifacts, memory=memory, delivery_intent=intent, require_review=require_review))
    scope = lambda: native_memory_scope(owner, memory_workspace, access_check=check, allow_remote_search=False)
    # Same task's isolated replays share immutable payloads, not mutable
    # conversation/history or working-note state. Native ACP owns that history.
    async with business_checkpointer(business_directory / 'business-checkpoint.sqlite',
            object_path=directory / 'business-objects.sqlite') as saver:
        consultations = None
        if options.get('allow_agent_consultation'):
            from .harness_consultations import HarnessConsultations
            reviewer = options.get('answer_review_model')
            if reviewer != 'gpt-6.1-sol' or reviewer not in budget.prices or not environment.get('OPENAI_API_KEY'):
                raise ValueError('consultation_provider_not_admitted')
            consultations = HarnessConsultations(directory=business_directory/'consultations', saver=saver,
                grants=list(grants), tid=tid, rid=rid, check=check, scope=scope, budget=budget,
                environment=environment, model=reviewer, basis=options['token_budget_basis'],
                as_of=organization.research_as_of, public_sink=phase_arguments['public_sink'])
            grants.extend(consultations.tools())
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id=tid, check=check, scope=scope,
            stop_on_tool_error=options.get('stop_on_tool_error') is True, note_versions=memory.export_markdown)
        if consultations:
            consultations.parent = bridge
        action = grant.get('report_action_request', {})
        failed_ids = None
        if options.get('stop_on_tool_error') is True and action.get('action') == 'recover':
            from uuid import UUID
            from .harness_business_tools import failed_run_receipts
            events = session_directory / str(UUID(action['previous_run_id'])) / 'events.private.jsonl'
            failed_ids = await asyncio.to_thread(failed_run_receipts, events)
        recovery_receipt = await bridge.initialize({**({} if clean_import else admitted), 'question': grant['question']},
            recovering=action.get('action') == 'recover', failed_receipt_ids=failed_ids)
        if recovery_receipt:
            _persist(run_directory / 'tool-recovery.json', recovery_receipt)
        if options.get('legacy_receipt_import'):
            from .harness_legacy_import import legacy_receipts
            await asyncio.to_thread(check)
            imported = await asyncio.to_thread(legacy_receipts, options['legacy_receipt_import'], grant=grant)
            await bridge.import_receipts(imported)
            # A pinned branch may begin at an earlier failed batch while Java
            # admits the new command against the latest outer checkpoint.
            # Validate the branch's own failed calls using its imported history.
            if replay_origin_run and action.get('action') == 'recover' and options.get('stop_on_tool_error') is True:
                from uuid import UUID
                from .harness_business_tools import failed_run_receipts, restored_batch_feedback
                branch_state = await bridge.state()
                if branch_state.get('harness_command_id') in (None, grant.get('report_command_id')):
                    origin_events = directory / str(UUID(replay_origin_run)) / 'events.private.jsonl'
                    origin_ids = await asyncio.to_thread(failed_run_receipts, origin_events)
                    if not origin_events.is_file() or not origin_ids.issubset({m.tool_call_id for m in imported['messages']
                            if isinstance(m, ToolMessage) and m.status == 'error'}):
                        raise ValueError('harness_replay_failed_batch_checkpoint_mismatch')
                    recovery_receipt = restored_batch_feedback(imported['messages'], origin_ids) or recovery_receipt
                    if recovery_receipt:
                        _persist(run_directory / 'tool-recovery.json', recovery_receipt)
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
            receipts=run_directory / 'wire', wire_usage=lambda _: None, public_sink=phase_arguments['public_sink'],
            dispatch_lane='author' if consultations else None)
        key = environment[options['provider_key_env']]
        transport = HarnessProviderTransport(dispatch, protocol=options['protocol'], endpoint=options['provider_endpoint'],
            provider_headers={'Authorization': 'Bearer ' + key}, token=token)
        dispatch.wire_usage = transport.meter

        async def guard(state):
            return validate_work_input(state, check=check, grant=grant, admitted_values=admitted, expected_input=expected_input)

        from .answer_review import PREFIX, target, author_input, apply_response
        challenge = None
        command = grant.get('report_action_request', {})
        command_text = command.get('message', '')
        if command.get('action') == 'recover':
            historical = [m.content for m in admitted.get('messages', []) if m.type == 'human']
            if historical and historical[-1].startswith(PREFIX):
                command_text = historical[-1]
        if command_text.startswith(PREFIX):
            if intent not in ('answer', 'report') or not options.get('answer_review_model'):
                raise ValueError('selected_answer_review_not_enabled')
            author_binding = json.loads((session_directory / 'session-binding.json').read_text(encoding='utf8'))
            if author_binding['binding'] != binding:
                raise ValueError('selected_answer_author_binding_changed')
            current = await bridge.state()
            target_path = run_directory / 'review-target.json'
            if command.get('action') == 'recover':
                previous = directory / command['previous_run_id']
                pointer = previous / 'answer-review-origin.json'
                if pointer.exists():
                    previous = directory / json.loads(pointer.read_text(encoding='utf8'))['run_id']
                target_path = previous / 'review-target.json'
                if target_path.exists():
                    current = json.loads(target_path.read_text(encoding='utf8'))
            challenge = target(command_text, admitted['messages'], author_binding['session_id'],
                               report=current.get('report'), report_version=current.get('report_version'))
            if challenge[0].artifact != intent:
                raise ValueError('selected_review_artifact_intent_mismatch')
            if challenge[0].artifact == 'report' and not target_path.exists():
                _persist(target_path, {k: current[k] for k in ('report', 'report_version')})

        async def project(state, result):
            if consultations:
                await consultations.ensure_finished()
            business = await bridge.state()
            from .task_outcome import TaskOutcome
            from .source_references import render_answer_references
            delivered = result['text']
            annotations = {}
            if challenge:
                selected, original = challenge
                review = json.loads(opinion_path.read_text(encoding='utf8'))
                if selected.artifact == 'report':
                    response = {'artifact': 'report', 'reviewed_report_version': original.additional_kwargs['report_version'],
                                'revised_report_version': business.get('report_version'),
                                'author_response': delivered}
                else:
                    delivered, response = apply_response(original.content, delivered)
                annotations['answer_review'] = {**review, **response, 'version': selected.version,
                                                'quote': selected.quote, 'question': selected.question}
            text, citations, unresolved = render_answer_references(delivered, business)
            if challenge:
                citations = {**{k:v for k,v in original.additional_kwargs.get('citation_bindings', {}).items()
                                if k in text}, **citations}
            from .conversation_tools import calculator_observations
            messages = business.get('messages', [])
            advisory = audit_changes(original.content if challenge else prior_answer, text, calculator_observations(messages),
                                     earlier_notes=saved_note_wording(messages))
            output = AIMessage(content=text, additional_kwargs={**annotations, 'harness_session_id': result['session_id'],
                'citation_bindings': citations, 'unresolved_citations': unresolved, 'quantitative_change_check': advisory})
            # Financial observations stay in the existing export/readback
            # projection. They are not transplanted into native ACP history.
            before = {m.id for m in state.get('messages', []) if m.id}
            receipts = [m for m in business.get('messages', []) if m.id not in before]
            delivery = business.get('delivery')
            if result.get('status') == 'completed' and result.get('text'):
                _persist(last_delivery, {'run_id': result.get('reused_from_run', rid),
                                         **({'answer_version': canonical_sha256(text)} if challenge and challenge[0].artifact == 'answer' else {})})
            submitted = bool(delivery) or (intent == 'answer' and bool(result['text']))
            return {**{k: business[k] for k in ('report', 'report_version', 'delivery') if k in business},
                'messages': [*receipts, output], 'task_outcome': TaskOutcome(task_id=tid, run_id=rid,
                execution_status='submitted' if submitted else 'incomplete', phase='harness_result',
                artifact_status='submitted' if submitted else 'none', artifact_kind=intent if submitted else None,
                artifact_digest=delivery['artifact_digest'] if delivery else canonical_sha256(delivered),
                author_note_status='missing').model_dump(mode='json')}

        review_command = command.get('previous_run_id') if challenge and command.get('action') == 'recover' else rid
        opinion_path = run_directory / 'answer-review.json'
        predecessor_opinion = directory / review_command / 'answer-review.json'
        async def work(state):
            nonlocal review_context
            binding = {'execution_id': tid, 'manifest_digest': grant['manifest_digest'],
                       'release': options['binary_sha256'], 'model': options['model']}
            action = grant.get('report_action_request', {})
            await bridge.begin_command(grant.get('report_command_id', rid),
                recovering=action.get('action') == 'recover')
            if action.get('action') == 'recover':
                if challenge and predecessor_opinion.exists() and not opinion_path.exists():
                    _persist(opinion_path,json.loads(predecessor_opinion.read_text(encoding='utf8')))
                recovered = completed_recovery(session_directory, previous_run_id=action['previous_run_id'], binding=binding)
                if recovered is not None:
                    _persist(run_directory / 'turn.private.json', {**recovered, 'reused_from_run': action['previous_run_id']})
                    return await project(state, {**recovered, 'reused_from_run': action['previous_run_id']})
                if consultations:
                    await consultations.recover_cancelled(action['previous_run_id'],phase_arguments['settings']['audit_root'])
            if challenge:
                selected, original = challenge
                if not opinion_path.exists():
                    review_id = grant['report_command_id']
                    original_scope = None
                    if action.get('action') == 'recover':
                        predecessor = await native.runs.get(tid, action['previous_run_id'])
                        pointer = directory / action['previous_run_id'] / 'answer-review-origin.json'
                        if pointer.exists():
                            origin = json.loads(pointer.read_text(encoding='utf8'))
                            predecessor = await native.runs.get(tid, origin['run_id'])
                        elif not predecessor.get('kwargs', {}).get('input'):
                            # Rolling upgrade: legacy resume ran with input=None.
                            # Resolve only a unique matching, admitted command.
                            recent = await native.runs.list(tid, limit=20)
                            matches = []
                            for row in recent:
                                if row['created_at'] > predecessor['created_at']:
                                    continue
                                candidate = await native.runs.get(tid, row['run_id'])
                                ms = (candidate.get('kwargs', {}).get('input') or {}).get('messages') or []
                                if ms and ms[-1].get('content') == command_text:
                                    matches.append(candidate)
                            if len(matches) != 1:
                                raise ValueError('answer_review_origin_not_unique')
                            predecessor = matches[0]
                        review_id = predecessor['metadata']['organization_report_action']['report_command_id']
                        original_scope = tid + ':' + predecessor['run_id']
                    _persist(run_directory / 'answer-review-origin.json',
                             {'run_id': original_scope.split(':')[-1] if original_scope else rid})
                    from .answer_review_provider import independent_review
                    model = options['answer_review_model']
                    opinion = await independent_review(selected=selected, message=original, question=grant['question'],
                        bridge=bridge, budget=budget, environment=environment, model=model, scope=tid+':'+rid,
                        command_id=review_id, authority=dispatch_authority, basis=options['token_budget_basis'],
                        as_of=organization.research_as_of, public_sink=phase_arguments['public_sink'], previous_scope=original_scope,
                        audit_root=phase_arguments['settings']['audit_root'],
                        predecessor_scope=tid+':'+action['previous_run_id'] if action.get('action')=='recover' else None)
                    _persist(opinion_path, {'reviewer': model, 'opinion': opinion})
                review = json.loads(opinion_path.read_text(encoding='utf8'))
                review_context = (original.content, review['opinion'])

            async with harness_local_services(business=bridge, dispatch=dispatch, transport=transport, token=token) as endpoint:
                prompt = research_system_prompt(bridge.tools, 'Research as of: ' + organization.research_as_of +
                    '\nRequested delivery: ' + intent + '. Save useful working understanding as needed; only deliver the requested artifact form.'+
                    '\nUse returned citation_handle values in source_id fields and [REF-...] citations. They bind exact observed originals/calculations; do not shorten them further. Original long IDs remain compatible.') + method_content
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
                        authority=active_authority, stop=bridge.stop, mcp_servers=servers,
                        workspace=directory if replay_origin_run else session_directory) as session:
                    request = author_input(selected, original, review['opinion']) if challenge else state['messages'][-1].content
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
        try:
            yield graph.compile(name='research_session')
        finally:
            if consultations:
                await consultations.close()
