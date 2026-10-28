"""Admitted organization host for the shared continuous parent.

No dispatch or admission is performed here. The caller has validated a durable
command and keeps the existing organization data factory alive for this run.
"""
from contextlib import asynccontextmanager
from copy import deepcopy
import json
from types import SimpleNamespace

from langchain_core.tools import tool, ToolException
from langgraph.prebuilt import ToolRuntime
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

from .conversation_agent import GrantedTool
from .on_demand_research import OnDemandResearchState


def artifact_reader(data, navigation, question_state):
    """Revalidate native tool artifacts, never model prose or browser records."""
    from .case_artifacts import CaseArtifacts
    from .conversation_handoff import observed_sources
    sources = observed_sources({'values': {'messages': [m.model_dump(mode='json') if hasattr(m, 'model_dump') else m
                                                       for m in question_state.get('messages', [])]}})
    validated = navigation.restore([{'status': 'success', 'content': list(sources.values())}])
    result = CaseArtifacts.from_observed_sources(validated, case_id=data.foundation_binding.case_id,
                                                 research_as_of=data.foundation_binding.research_as_of)
    for key in ('snapshot_id', 'foundation_digest'):
        setattr(result, key, getattr(data.foundation_binding, key))
    result.owner_data_gate_decision_digest = data.decision_digest
    result.source_route_catalog_digest = data.source_route_catalog_digest
    result.inventory_snapshot_digest = data.inventory_snapshot_digest
    return result


@asynccontextmanager
async def organization_work_session(*, native, resources, authority, check, organization, phase_arguments,
                                    config, grant, expected_input, environment):
    from . import research_session_runtime as host
    from .conversation_tools import conversation_tools
    from .case_review_agent import CaseModelAudit, case_chat_model
    from .deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
    from .conversation_summary import summary_middleware
    from .delegated_task_host import admitted_delegation_tools
    from .delegated_task_graph import current_work_catalog
    from .working_memory import WorkingMemory
    from .working_memory_tools import native_memory_scope, working_memory_tools
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation

    tid, rid = phase_arguments['thread_id'], phase_arguments['run_id']
    checkpoint = grant.get('report_action_request', {}).get('checkpoint_id')
    admitted_values = (await native.threads.get_state(tid, **({'checkpoint_id': checkpoint} if checkpoint else {}))).get('values') or {}
    owner = 'organization:' + grant['organization_id']
    execution = phase_arguments['execution']
    if checkpoint:
        # Only the current Java-signed user command can select a new deliverable;
        # source scope, model configuration and budget remain inherited.
        from .execution_options import ExecutionOptions
        current = grant['report_action_request']
        execution = ExecutionOptions.model_validate({**execution.model_dump(mode='json'),
            'delivery_intent': current['delivery_intent'], 'require_report_review': current['require_report_review']})
    spec = json.loads((phase_arguments['root'] / 'configs/research/runtime/conversation.json').read_text(encoding='utf8'))
    spec = deepcopy(spec)
    # Parent and professional operations share the configured research model;
    # conversation's optional summary remains independently budgeted.
    node = execution.apply_profile(phase_arguments['profile'])['nodes']['lead']
    spec['profile'] = node['profile']
    spec['budget'] = {**node['budget'], 'node_purpose': 'Continuous research partner: answer the current question, maintain working results and choose optional operations only as needed.',
        'input_scale': 'Current native task, scoped source windows, saved work versions and optional operation receipts.',
        'required_outputs': ['Requested answer, saved working paper or report; preserve evidence, periods and units.',
                             'Use optional delegation/checking/composition when it advances the current question.']}
    profile = DeepSeekModelProfile.model_validate(spec['profile'])
    basis = TokenBudgetBasis.model_validate_json(json.dumps(spec['budget']))
    budget = phase_arguments['budget_scope']
    if budget is None:
        raise ValueError('on_demand_requires_shared_root_budget')
    audit = CaseModelAudit(actor='research_partner', profile=profile, basis=basis,
        public_sink=phase_arguments['public_sink'], private_sink=phase_arguments['private_sink'],
        stream_public=True, source_access_check=check, dispatch_guard=budget.guard('lead', profile))
    model = case_chat_model(profile, basis, SimpleNamespace(base_url='https://api.deepseek.com'),
        phase_arguments['api_key'], streaming=True, context_editing=spec.get('context_editing'))
    memory = WorkingMemory(environment['FINSIGHT_WORKING_MEMORY_PATH'], owner=owner, workspace=tid,
        actor='research_partner', access_check=check, allow_remote_search=False)
    navigation = (organization.retrieval.navigation() if organization.retrieval else
        OrganizationSourceNavigation(organization.reader, workbench_url=organization.workbench_url))
    grants = conversation_tools(thread_id=tid)

    @tool(response_format='content_and_artifact')
    def read_source_document(request: SourceDocumentRequest):
        """Search/catalog/read the task's authorized fixed originals. Candidate IDs are not citations until read."""
        check()
        result = navigation.navigate(request)
        body = result.model_dump(mode='json') if hasattr(result, 'model_dump') else result
        check()
        return json.dumps(body, ensure_ascii=False), body

    grants.append(GrantedTool(read_source_document, 'read', '当前组织任务的固定资料及当前权限'))
    grants.extend(GrantedTool(t, 'working_note_write' if t.name == 'WriteWorkingNote' else 'read',
        '当前组织任务的版本化工作笔记') for t in working_memory_tools('research_partner', owner=owner, workspace=tid))
    grants.extend(await admitted_delegation_tools(sdk=native, resources=resources, run_authority=authority,
        root_thread_id=tid, root_run_id=rid, specification=spec, settings=phase_arguments['settings'], environment=environment))
    summary = summary_middleware(spec, public=phase_arguments['public_sink'], private=phase_arguments['private_sink'],
        access_check=check, budget_scope=budget)
    audit.working_note_context = lambda: current_work_catalog(memory)
    with organization(run_invocation_id='on-demand:' + rid, source_read_enabled=True) as data:
        reader = lambda state: artifact_reader(data, navigation, state)
        @tool
        def read_research_source(source_id: str, runtime: ToolRuntime, offset: int = 0, max_characters: int = 4000):
            """Read one source ID from the observed_sources catalog. Rechecks current source authority; preserves original identity and exact paging."""
            from .case_artifacts import read_source_window
            if offset < 0 or not 100 <= max_characters <= 12000:
                raise ToolException('invalid_source_read_window')
            check()
            sources = reader(runtime.state).source_snapshot()
            if source_id not in sources:
                raise ToolException('source_not_observed_read_current_source_catalog')
            result = read_source_window(source_id, sources[source_id], offset, max_characters)
            check()
            return result
        read_research_source.handle_tool_error = True
        grants.append(GrantedTool(read_research_source, 'read', '已观察来源的当前授权回读'))
        parent = host.create_on_demand_research_agent(model=model, grants=grants, execution=execution,
            phase_arguments={k: v for k, v in phase_arguments.items() if k != 'execution'}, artifact_reader=reader, permission_mode='request_standard',
            middleware=[summary, audit], working_memory=memory, server_managed_persistence=True,
            task_context='Research as of: '+organization.research_as_of+'. Use read_source_document to discover the authorized source catalog.',
            **spec['limits'])

        async def guard(state, config: RunnableConfig):
            check()
            # Inputs are frozen at the business command. The saved history may
            # grow, but callers cannot replace the task or inject source objects.
            if state.get('question') != grant['question']:
                raise ValueError('organization_work_question_mismatch')
            messages = state.get('messages', [])
            # A forged native input must not replace saved reports, findings,
            # observations or task status while retaining a plausible question.
            for key in set(state) | set(admitted_values):
                if key not in {'messages', 'question'} and state.get(key) != admitted_values.get(key):
                    raise ValueError('organization_work_state_injection:' + key)
            if expected_input is None:
                from langchain_core.messages import convert_to_messages, message_to_dict, messages_from_dict
                before = [messages_from_dict([{'type': m['type'], 'data': m}])[0]
                          if isinstance(m, dict) and m.get('type') in {'human', 'ai', 'system', 'tool', 'function', 'chat'}
                          else convert_to_messages([m])[0] for m in admitted_values.get('messages', [])]
                if ([message_to_dict(m) for m in messages[:-1]] != [message_to_dict(m) for m in before]):
                    raise ValueError('organization_work_history_injection')
            if expected_input is not None and (len(messages) != 1 or messages[0].content != grant['question']
                    or getattr(messages[0], 'type', None) != 'human'):
                raise ValueError('organization_work_initial_input_mismatch')
            if expected_input is None and (not messages or getattr(messages[-1], 'type', None) != 'human'
                    or messages[-1].content != grant['report_action_request']['message']):
                raise ValueError('organization_work_continuation_input_mismatch')
            return {}

        graph = StateGraph(OnDemandResearchState)
        graph.add_node('admitted_input', guard)
        graph.add_node('work', parent)
        graph.add_edge(START, 'admitted_input')
        graph.add_edge('admitted_input', 'work')
        graph.add_edge('work', END)
        with native_memory_scope(owner, tid, access_check=check, allow_remote_search=False):
            yield graph.compile(name='research_session')
