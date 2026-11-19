"""Native child graph using the shared conversation agent, tools and memory.

Independent command admission precedes any model/resource use. The execution
checkpoint owns reads and proposals; only selected original references cross
the parent/child boundary. The child cannot recursively delegate.
"""
from contextlib import asynccontextmanager
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime
from pydantic import SecretStr

from .conversation_agent import build_conversation_agent, GrantedTool
from .delegated_task_contract import child_task_context, validate_fixed_input
from .delegated_task_runtime import SURFACE


def child_tools(*, fixed_input, sdk, owner, child, run, memory, parent_memory, check, navigation=None):
    from .conversation_tools import conversation_tools
    from .conversation_handoff import handoff_tools
    from .working_memory_tools import working_memory_tools
    from .delegated_task_tools import completion_tool
    from sec_agent.research_foundation.research_methods import get_research_method
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    from langchain_core.tools import tool

    task = fixed_input['task']
    def method(identifier):
        from .research_graph_contracts import canonical_sha256
        if not identifier:
            catalog = get_research_method()
            return {**catalog, 'methods': [m for m in catalog['methods'] if m['method_id'] in fixed_input['method_digests']]}
        if identifier not in fixed_input['method_digests']:
            raise ValueError('method_not_available_for_child')
        value = get_research_method(identifier)
        if canonical_sha256(value) != fixed_input['method_digests'][identifier]:
            raise ValueError('delegated_method_version_changed')
        return value
    grants = conversation_tools(thread_id=child, method_reader=method)
    reference = {'source_thread': fixed_input['source_thread'], 'checkpoint_id': fixed_input['checkpoint_id'],
                 'selected_materials': task['materials'], 'working_notes': task['working_notes']}
    grants.extend(handoff_tools(reference=reference, sdk=sdk, owner_id=owner, access_check=check,
        note_reader=lambda note, version, offset: parent_memory.read(note, version=version, offset=offset)))
    grants.extend(GrantedTool(t, 'working_note_write' if t.name == 'WriteWorkingNote' else 'read',
                             '当前子任务的版本化工作底稿')
                  for t in working_memory_tools('delegated_task', owner=owner, workspace=child))
    if navigation is not None:
        @tool(response_format='content_and_artifact')
        def read_source_document(request: SourceDocumentRequest):
            """Search or read the authorized fixed organization snapshot, using its existing reader."""
            check()
            result = navigation.navigate(request)
            body = result.model_dump(mode='json') if hasattr(result, 'model_dump') else result
            check()
            return json.dumps(body, ensure_ascii=False), body
        grants.append(GrantedTool(read_source_document, 'read', '根任务授权的固定资料版本'))
    grants.append(completion_tool(fixed_input=fixed_input, child_thread_id=child, run_id=run,
                                  memory=memory, access_check=check))
    return grants


@asynccontextmanager
async def delegated_task_session_graph(config: RunnableConfig, runtime: ServerRuntime):
    if runtime.execution_runtime is None:
        yield build_conversation_agent(model=FakeMessagesListChatModel(responses=[]), grants=[],
                                       permission_mode='request_standard', checkpointer=None)
        return
    if os.getenv('FINSIGHT_ORGANIZATION_TASK_ACTIONS_ENABLED') != '1':
        raise ValueError('delegated_task_execution_not_enabled')
    from .agent_server_entry import _require_langsmith_execution_environment
    _require_langsmith_execution_environment(config)
    from langgraph_sdk import get_client
    from .delegated_task_authority import OrganizationTaskAuthority
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionReader
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    from sec_agent.research_foundation.asset_workspace import AssetWorkspace
    from .research_budget import budget_from_host
    from .working_memory import WorkingMemory
    from .working_memory_tools import native_memory_scope
    from .deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
    from .case_review_agent import CaseModelAudit, case_chat_model
    from .report_session import session_audit_sinks
    ids = config['configurable']
    child, run = str(UUID(ids['thread_id'])), str(UUID(ids['run_id']))
    sdk = get_client(api_key=None)
    retrieval = None
    try:
        thread = await sdk.threads.get(child)
        if thread['metadata'].get('surface') != SURFACE:
            raise ValueError('delegated_task_surface_mismatch')
        binding = thread['metadata']['delegated_task']
        fixed = binding['fixed_input']; validate_fixed_input(fixed)
        if binding['execution_id'] != str(UUID(ids['delegated_execution_id'])):
            raise ValueError('delegated_task_root_mismatch')
        resources = OrganizationExecutionAuthority(base_url=os.environ['FINSIGHT_BUSINESS_API_URL'],
            network_profile=os.getenv('FINSIGHT_ORGANIZATION_AUTHORITY_NETWORK', 'loopback'),
            secret=os.environ['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'], execution_id=binding['execution_id'],
            manifest_digest=fixed['manifest_digest'])
        authority = OrganizationTaskAuthority(resources)
        def check():
            grant = authority.admit(child, str(UUID(ids['delegated_command_id'])), run)
            if grant['binding'] != binding or grant['owner_id'] != thread['metadata']['owner_id']:
                raise ValueError('delegated_admission_changed')
            return grant
        grant = await asyncio.to_thread(check)
        actual = await sdk.runs.get(child, run)
        from .delegated_task_runtime import dispatch_arguments
        from .research_graph_contracts import canonical_sha256
        expected = dispatch_arguments(grant['command'])
        if (actual.get('metadata', {}).get('delegated_operation_id') != grant['operation_id']
                or actual.get('metadata', {}).get('delegated_command_id') != grant['command_id']
                or actual.get('metadata', {}).get('dispatch_digest') != canonical_sha256(expected)):
            raise ValueError('delegated_run_not_dispatched_by_command')
        root = Path(os.environ['FIN_REPO_ROOT'])
        settings = json.loads(Path(os.environ['FINSIGHT_REPORT_SESSION_SETTINGS']).read_text(encoding='utf8'))
        owner = grant['owner_id']
        budget = await asyncio.to_thread(budget_from_host, settings, thread_id=binding['execution_id'],
                                         metadata={'owner_id': owner}, environment=os.environ)
        if budget is None or budget.budget != fixed['root_budget_id']:
            raise ValueError('delegated_root_budget_not_bound')
        spec = fixed['runtime_configuration']
        profile = DeepSeekModelProfile.model_validate(spec['profile'])
        basis = TokenBudgetBasis.model_validate_json(json.dumps(spec['budget']))
        public, private = session_audit_sinks(Path(settings['audit_root']) / child / run)
        audit = CaseModelAudit(actor='delegated_task', profile=profile, basis=basis,
            public_sink=public, private_sink=private, stream_public=True, source_access_check=check,
            dispatch_guard=budget.guard('conversation', profile))
        model = case_chat_model(profile, basis, SimpleNamespace(base_url='https://api.deepseek.com'),
                                SecretStr(os.environ['DEEPSEEK_API_KEY']), streaming=True,
                                context_editing=spec.get('context_editing'))
        memory = WorkingMemory(os.environ['FINSIGHT_WORKING_MEMORY_PATH'], owner=owner, workspace=child,
            actor='delegated_task', access_check=check, allow_remote_search=False)
        parent_memory = WorkingMemory(os.environ['FINSIGHT_WORKING_MEMORY_PATH'], owner=owner,
            workspace=binding['execution_id'], actor='handoff-reader', access_check=check, allow_remote_search=False)
        reader = OrganizationExecutionReader(AssetWorkspace(Path(os.environ['FINSIGHT_ORGANIZATION_ASSETS_ROOT'])), resources)
        resource_grant, manifest, _ = await asyncio.to_thread(reader._grant)
        if manifest.get('retrieval_index') is not None:
            from sec_agent.research_foundation.organization_retrieval_lifecycle import OrganizationRetrievalLifecycle
            retrieval = OrganizationRetrievalLifecycle(reader, workbench_url=settings['workbench_url'],
                retrieval_root=os.getenv('FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT'), grant=resource_grant)
            await asyncio.to_thread(retrieval.prepare)
            navigation = retrieval.navigation()
        else:
            navigation = OrganizationSourceNavigation(reader, workbench_url=settings['workbench_url'])
        grants = child_tools(fixed_input=fixed, sdk=sdk, owner=owner, child=child, run=run,
                             memory=memory, parent_memory=parent_memory, check=check, navigation=navigation)
        context = ('Delegated baseline and selected originals: ' + json.dumps(child_task_context(fixed), ensure_ascii=False)
                   + '\nCurrent admitted request: ' + json.dumps({key: grant['command'][key]
                       for key in ('command_id', 'action', 'message')}, ensure_ascii=False)
                   + '\nUse complete_delegated_task to return your answer or saved workpaper. '
                     'A working-note save is progress, not submission or independent review.')
        from .conversation_summary import summary_middleware
        summary = summary_middleware(spec, public=public, private=private, access_check=check, budget_scope=budget)
        audit.working_note_context = lambda: current_work_catalog(memory)
        with native_memory_scope(owner, child, access_check=check, allow_remote_search=False):
            yield build_conversation_agent(model=model, grants=grants, permission_mode='request_standard',
                checkpointer=None, middleware=[summary, audit], server_managed_persistence=True,
                task_context=context, **spec['limits'])
    finally:
        if retrieval is not None:
            await asyncio.to_thread(retrieval.close)
        await sdk.aclose()


def current_work_catalog(memory):
    """Current version pointers, never selecting a draft or copying old prose."""
    rows = memory.manifest()
    return json.dumps({'current_workpapers': rows[:20], 'catalog_only_not_reviewed': True,
        'more': len(rows) > 20,
        'readback': 'ReadWorkingNote(note_id=id, version=version); SearchWorkingNotes for more'}, ensure_ascii=False)
