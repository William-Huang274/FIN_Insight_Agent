"""Actual SQLite/tool surfaces under fixed Java grants; no model or retrieval API."""
import asyncio
from contextvars import copy_context

import pytest

from sec_agent.agent_runtime.organization_memory_scope import organization_memory_scope
from sec_agent.agent_runtime.working_memory import WorkingMemory, WorkingMemoryAccessDenied
from sec_agent.agent_runtime.working_memory_tools import execute_memory_tool, memory_for, native_memory_scope
from sec_agent.agent_runtime.user_workpaper_context import current_scope_revision_prompt, human_revision_catalog
from test_organization_research_inputs import fixture
from test_organization_execution_access import runtime_at, runtime_grant


@pytest.fixture
def scoped(tmp_path, monkeypatch):
    shared, preparation = fixture(tmp_path)
    grant = runtime_grant(preparation)
    reader, state = runtime_at(shared, grant)
    path = tmp_path / 'working-papers.sqlite'
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH', str(path))
    monkeypatch.setenv('FINSIGHT_AUTH_MODE', 'oidc_product')
    return reader, state, path


def config(reader):
    return {'configurable': {'thread_id': reader.authority.execution_id}}


def save(reader, body='Private derived observation.'):
    return execute_memory_tool('WriteWorkingNote', {'title':'Analysis', 'body':body}, config(reader), 'lead')


def test_current_historical_export_revision_and_other_agents_share_only_this_execution(scoped):
    reader, state, path = scoped
    with organization_memory_scope(reader):
        first = save(reader)
        memory = memory_for(config(reader), 'lead')
        assert memory.owner == 'organization:' + state['grant']['organization_id']
        second = memory.save('Analysis', 'Human correction', 1, user_edit=True)
        colleague = memory_for(config(reader), 'reviewer')
        assert colleague.read(first['note_id'])['body'] == 'Human correction'
        assert colleague.read(first['note_id'], version=1)['body'] == 'Private derived observation.'
        assert colleague.export_markdown(first['note_id'])['markdown'] == 'Human correction'
        assert human_revision_catalog(colleague)['items'][0]['version'] == second['version']
        assert first['note_id'] in current_scope_revision_prompt('reviewer')
    # A fresh, authorized scope can resume persisted notes; personal ownership cannot.
    with organization_memory_scope(reader):
        assert memory_for(config(reader), 'lead').read(first['note_id'])['found']
    assert not WorkingMemory(path, owner='alice', workspace=reader.authority.execution_id,
                             actor='lead').read(first['note_id'])['found']


@pytest.mark.parametrize('fault', ['revoke', 'timeout', 'manifest'])
@pytest.mark.parametrize('operation', ['read', 'history', 'search', 'write', 'catalog', 'export', 'manifest'])
def test_existing_handle_rechecks_every_surface_and_failure_is_not_optional_memory_error(scoped, fault, operation):
    reader, state, _ = scoped
    with organization_memory_scope(reader):
        note = save(reader)
        memory = memory_for(config(reader), 'lead')
        if fault == 'revoke': state['status'] = 404
        if fault == 'timeout': state['timeout'] = True
        if fault == 'manifest': state['grant']['manifest_text'] += ' '
        calls = state['calls']
        actions = {
            'read': lambda: memory.read(note['note_id']),
            'history': lambda: memory.read(note['note_id'], version=1),
            'search': lambda: execute_memory_tool('SearchWorkingNotes', {}, config(reader), 'lead'),
            'write': lambda: save(reader, 'Cannot write after withdrawal'),
            'catalog': lambda: current_scope_revision_prompt('lead'),
            'export': lambda: memory.export_markdown(note['note_id']),
            'manifest': memory.manifest,
        }
        with pytest.raises(WorkingMemoryAccessDenied): actions[operation]()
        assert state['calls'] == calls + 1  # No positive ACL cache or automatic retry.


@pytest.mark.parametrize('override', ['owner', 'workspace', 'nested'])
def test_explicit_server_arguments_cannot_override_active_scope(scoped, override):
    reader, _, _ = scoped
    with organization_memory_scope(reader):
        with pytest.raises(WorkingMemoryAccessDenied):
            if override == 'nested':
                with native_memory_scope('alice', 'other'): pass
            else:
                execute_memory_tool('SearchWorkingNotes', {}, config(reader), 'lead', **{override:'other'})


def test_captured_handle_and_copied_context_expire_with_scope(scoped):
    reader, _, _ = scoped
    with organization_memory_scope(reader):
        memory = memory_for(config(reader), 'lead')
        inherited = copy_context()
        save(reader)
    with pytest.raises(WorkingMemoryAccessDenied): memory.search()
    with pytest.raises(WorkingMemoryAccessDenied): inherited.run(memory.search)


def test_nested_legacy_scope_cannot_enable_remote_search(scoped, monkeypatch):
    from sec_agent.agent_runtime import working_memory_search as search
    reader, state, _ = scoped
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_SEMANTIC', '1')
    monkeypatch.setattr(search, 'QwenRetrieval', lambda *a, **k: pytest.fail('organization text left the host'))
    with organization_memory_scope(reader):
        note = save(reader)
        with native_memory_scope('organization:' + state['grant']['organization_id'], reader.authority.execution_id):
            result = execute_memory_tool('SearchWorkingNotes', {'query':'derived'}, config(reader), 'lead')
            assert result['items'][0]['id'] == note['note_id']
            assert result['retrieval'] == 'literal_fulltext_current_workspace'
            memory = memory_for(config(reader), 'lead')
            with pytest.raises(WorkingMemoryAccessDenied): search.WorkingPaperSearch(memory).search('derived')


def test_revocation_during_io_hides_result_and_does_not_claim_write_rollback(scoped, monkeypatch):
    reader, state, _ = scoped
    with organization_memory_scope(reader):
        original_index = WorkingMemory._index
        def revoke_after_commit(db, note_id, title, body):
            original_index(db, note_id, title, body)
            state['status'] = 404
        monkeypatch.setattr(WorkingMemory, '_index', staticmethod(revoke_after_commit))
        with pytest.raises(WorkingMemoryAccessDenied): save(reader)
        # No automatic replay: after access restoration the committed version is still 1.
        state['status'] = 200
        memory = memory_for(config(reader), 'lead')
        assert memory.search()['items'][0]['version'] == 1
        # Denial after a successful SQL read must withhold the body as well.
        original = reader._after
        checks = []
        def revoke_on_second(grant):
            checks.append(1)
            if len(checks) == 2: state['status'] = 404
            return original(grant)
        monkeypatch.setattr(reader, '_after', revoke_on_second)
        with pytest.raises(WorkingMemoryAccessDenied): memory.search()


def test_concurrent_executions_and_to_thread_keep_independent_contexts(scoped, tmp_path):
    reader, _, _ = scoped
    shared, preparation = fixture(tmp_path / 'second')
    other, _ = runtime_at(shared, runtime_grant(preparation))
    async def work(current, text):
        with organization_memory_scope(current):
            note = await asyncio.to_thread(save, current, text)
            await asyncio.sleep(0)
            found = await asyncio.to_thread(execute_memory_tool, 'SearchWorkingNotes', {}, config(current), 'reviewer')
            assert [item['id'] for item in found['items']] == [note['note_id']]
            return note['note_id']
    async def exercise():
        return await asyncio.gather(work(reader, 'First organization'), work(other, 'Second organization'))
    first, second = asyncio.run(exercise())
    assert first != second
    with organization_memory_scope(reader):
        assert not memory_for(config(reader), 'lead').read(second)['found']


def test_distinct_executions_with_same_manifest_do_not_share_papers(scoped):
    from uuid import uuid4
    from copy import deepcopy
    reader, state, _ = scoped
    other_grant = deepcopy(state['grant'])
    other_grant['execution_id'] = other_grant['thread_id'] = str(uuid4())
    # The actual reader wrapper only needs the shared workspace attribute here.
    class Shared:
        workspace = reader.workspace
    other, _ = runtime_at(Shared(), other_grant)
    with organization_memory_scope(reader): note = save(reader)
    with organization_memory_scope(other):
        assert not memory_for(config(other), 'lead').read(note['note_id'])['found']


@pytest.mark.parametrize('revoke', [False, True])
def test_langgraph_tool_loop_preserves_scope_and_does_not_swallow_revocation(scoped, revoke):
    from langchain.agents import create_agent
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from sec_agent.agent_runtime.working_memory_tools import working_memory_tools
    reader, state, _ = scoped
    model_calls = []
    class ScriptedResearcher(BaseChatModel):
        @property
        def _llm_type(self): return 'static-organization-memory-fixture'
        def bind_tools(self, tools, **kwargs): return self
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            model_calls.append(1)
            observed = [message for message in messages if isinstance(message, ToolMessage)]
            if not observed:
                name, args = 'WriteWorkingNote', {'title':'Analysis', 'body':'Derived static note'}
            elif len(observed) == 1:
                if revoke: state['status'] = 404
                name, args = 'SearchWorkingNotes', {'query':'static'}
            else:
                assert 'Derived static note' in observed[-1].content
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='Static note read'))])
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content='', tool_calls=[{
                'name':name, 'args':args, 'id':str(len(observed)), 'type':'tool_call'}]))])
    async def exercise():
        with organization_memory_scope(reader):
            graph = create_agent(ScriptedResearcher(), tools=working_memory_tools('lead'))
            return await graph.ainvoke({'messages':[HumanMessage(content='Static memory exercise')]}, config(reader))
    if revoke:
        with pytest.raises(WorkingMemoryAccessDenied): asyncio.run(exercise())
        assert len(model_calls) == 2  # Tool failure stops the loop before a third model step.
    else:
        assert asyncio.run(exercise())['messages'][-1].content == 'Static note read'
