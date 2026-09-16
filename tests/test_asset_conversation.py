"""Asset conversation continuity; real storage, native API double, no paid calls."""
import asyncio
from copy import deepcopy
from uuid import uuid4

from test_asset_workspace import setup, selection, context
from test_project_research_materials import WRITE
from sec_agent.research_foundation.task_asset_updates import TaskAssetUpdates, TaskAssetView


def draft(tmp_path):
    client, service, calls, tid, workspace, project = setup(tmp_path)
    ref = selection(workspace, project)
    saved = context(client, ref)
    response = client.post('/api/v1/conversations/drafts', headers=WRITE, json={'asset_context_id': saved['context_id']})
    assert response.status_code == 200, response.text
    return client, service, calls, tid, workspace, project, ref


def test_submission_freezes_latest_memory_and_selected_input(tmp_path):
    client, service, calls, tid, workspace, project, ref = draft(tmp_path)
    workspace.save_profile('local-pilot', 'Read cash flow first.', 0)
    edited = client.post('/api/v1/asset-workspace/documents', headers=WRITE,
        json={'project_id': project, 'base_ref': ref, 'title': 'Revision', 'text': 'Revised user assumption 150.'})
    assert edited.status_code == 200
    new = next(a['current']['ref'] for a in workspace.catalog('local-pilot', project)['items'] if a['asset_id'] == ref['asset_id'])
    base = f'/api/v1/conversations/{tid}'
    prepared = client.post(base + '/asset-updates', headers=WRITE,
        json={'request_id': str(uuid4()), 'base_revision': 0, 'ref': new})
    assert prepared.status_code == 200, prepared.text
    assert client.get(base + '/asset-updates').json()['pending']
    sent = client.post(base + '/messages', headers=WRITE, json={'message': 'Read the revised assumption.'})
    assert sent.status_code == 200, sent.text
    config = deepcopy(calls[-1][2]['config']['configurable'])
    assert config['finsight_asset_memory'] == {'version': 1, 'body': 'Read cash flow first.'}
    workspace.save_profile('local-pilot', 'New preference after queueing.', 1)
    updates = TaskAssetUpdates(service.attachment_store.root)
    run = str(uuid4()); updates.pin(tid, run, config['finsight_asset_revision'])
    view = TaskAssetView(updates.store.root, tid, run)
    assert view.list(tid)[0]['project_origin']['document_id'] == new['version_id']
    assert config['finsight_asset_memory']['version'] == 1
    assert client.get(base + '/asset-updates').json()['active_revision'] == 1
    assert workspace.profile_history('bob')['items'] == []
    history = client.get('/api/v1/asset-workspace/profile/history').json()['items']
    assert [r['version'] for r in history] == [2, 1]
    assert client.get('/api/v1/asset-workspace/profile/history?offset=-1').status_code == 422


def test_discussion_handoff_is_pinned_unverified_and_keeps_original_sources(tmp_path, monkeypatch):
    client, service, calls, tid, workspace, project, ref = draft(tmp_path)
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH',str(tmp_path/'notes.sqlite'))
    memory=WorkingMemory(tmp_path/'notes.sqlite',owner='local-pilot',workspace=tid,actor='conversation')
    note=memory.save('Assumption','Old assumption')
    memory.save('Assumption','Human corrected period after the last chat.',1,user_edit=True)
    WorkingMemory(tmp_path/'notes.sqlite',owner='bob',workspace=tid,actor='conversation').save('Private','OTHER_OWNER_PRIVATE')
    checkpoint = str(uuid4())
    state = {'checkpoint': {'checkpoint_id': checkpoint}, 'values': {'messages': [
        {'id': 'user', 'type': 'human', 'content': 'Explain this working assumption and check its sources.'},
        {'id': 'ai', 'type': 'ai', 'content': [{'type': 'reasoning', 'text': 'PRIVATE_REASONING'},
            {'type': 'text', 'text': 'Unverified answer, not a source.'}],
            'additional_kwargs': {'reasoning_content': 'PRIVATE_REASONING'}}]}, 'tasks': []}
    async def get_state(_): return deepcopy(state)
    service.sdk.threads.get_state = get_state
    path = f'/api/v1/conversations/{tid}/research-context'
    body = {'checkpoint_id': checkpoint, 'question': 'Check the original financial evidence for this question.'}
    assert client.post(path, headers=WRITE, json={**body, 'checkpoint_id': str(uuid4())}).status_code == 409
    response = client.post(path, headers=WRITE, json=body)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['refs'][0] == ref and len(saved['refs']) == 2
    text = workspace.read('local-pilot', saved['refs'][1])['text']
    assert checkpoint in text and 'Unverified answer' in text and '未核验' in text
    assert 'PRIVATE_REASONING' not in text
    assert 'Human corrected period after the last chat.' in text and 'OTHER_OWNER_PRIVATE' not in text
    assert not any(c[0] == 'run' for c in calls)
    again = client.post(path, headers=WRITE, json=body).json()
    assert again['refs'] == saved['refs']  # No duplicate snapshot on a retry.
    memory.save('Assumption','A still newer human assumption.',2,user_edit=True)
    changed=client.post(path,headers=WRITE,json=body).json()
    assert changed['refs'][-1] != saved['refs'][-1]
    assert 'Human corrected period after the last chat.' in workspace.read('local-pilot',saved['refs'][-1])['text']
    assert 'A still newer human assumption.' in workspace.read('local-pilot',changed['refs'][-1])['text']
    uploaded = service.attachment_store.add(tid, 'Additional.md', b'Additional original must accompany the discussion.')
    expanded = client.post(path, headers=WRITE, json=body)
    assert expanded.status_code == 200, expanded.text
    refs = expanded.json()['refs']
    assert len(refs) == 3
    assert workspace.read('local-pilot', refs[1])['text'] == 'Additional original must accompany the discussion.'
    assert uploaded['document_id'] in workspace.read('local-pilot', refs[2])['text']
    workspace.library.set_access('local-pilot', project, 'document', ref['version_id'], True)
    assert client.post(path, headers=WRITE, json=body).status_code == 409


def test_approval_continuation_keeps_original_memory_snapshot(tmp_path):
    client, service, calls, tid, workspace, project, ref = draft(tmp_path)
    checkpoint = str(uuid4())
    snapshot = {'finsight_asset_revision': 0, 'finsight_asset_memory': {'version': 0, 'body': ''}}
    workspace.save_profile('local-pilot', 'Changed while awaiting approval.', 0)
    state = {'checkpoint': {'checkpoint_id': checkpoint}, 'values': {}, 'tasks': [
        {'interrupts': [{'id': 'approval', 'value': {'action_requests': [{'name': 'tool', 'args': {}}]}}]}]}
    async def get_state(_): return state
    async def runs(*a, **kw): return [{'status': 'success', 'metadata': {
        'model': 'deepseek-v4-flash', 'permission_mode': 'request_standard', 'asset_input': snapshot}}]
    service.sdk.threads.get_state, service.sdk.runs.list = get_state, runs
    response = client.post(f'/api/v1/conversations/{tid}/approvals', headers=WRITE,
        json={'checkpoint_id': checkpoint, 'interrupt_id': 'approval', 'decisions': ['reject']})
    assert response.status_code == 200, response.text
    assert calls[-1][2]['config']['configurable']['finsight_asset_memory'] == snapshot['finsight_asset_memory']


def test_native_runtime_consumes_pinned_sources_and_memory(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage, HumanMessage
    from tests.integration.fixtures.asset_conversation_script import ScriptedModel
    from sec_agent.agent_runtime import conversation_runtime as runtime
    client, service, calls, tid, workspace, project, ref = draft(tmp_path)
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'audit_root': str(tmp_path / 'audit')}))
    monkeypatch.setenv('FIN_REPO_ROOT', str(Path.cwd()))
    monkeypatch.setenv('FINSIGHT_RESEARCH_SESSION_ENABLED', '1')
    monkeypatch.setenv('FINSIGHT_REPORT_SESSION_SETTINGS', str(settings))
    monkeypatch.setenv('FINSIGHT_TASK_ATTACHMENTS_ROOT', str(service.attachment_store.root))
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fixture-not-a-credential')
    monkeypatch.delenv('FINSIGHT_WORKING_MEMORY_PATH', raising=False)
    monkeypatch.setattr('sec_agent.agent_runtime.agent_server_entry._require_langsmith_execution_environment', lambda _: None)
    # budget_from_host is synchronous, called in to_thread.
    monkeypatch.setattr('sec_agent.agent_runtime.research_budget.budget_from_host', lambda *a, **kw: None)
    async def close(): pass
    service.sdk.aclose = close
    monkeypatch.setattr('langgraph_sdk.get_client', lambda **kw: service.sdk)
    contexts = []
    class RecordingModel(ScriptedModel):
        def _generate(self, messages, *args, **kwargs):
            from langchain_core.outputs import ChatGeneration, ChatResult
            contexts.append(deepcopy(messages))
            index = sum(isinstance(m, AIMessage) for m in messages)
            return ChatResult(generations=[ChatGeneration(message=self.responses[index])])
    doc = service.attachment_store.list(tid)[0]
    model = RecordingModel(responses=[AIMessage(content='', tool_calls=[{'id': 'read', 'name': 'read_task_material',
        'args': {'request': {'source_space': 'uploads', 'operation': 'read', 'document_id': doc['document_id']}}}]),
        AIMessage(content='Scripted delivery, no financial acceptance.')])
    monkeypatch.setattr(runtime, 'case_chat_model', lambda *a, **kw: model)
    workspace.save_profile('local-pilot', 'A later preference that must not replace the queued input.', 0)
    run = str(uuid4())
    config = {'configurable': {'thread_id': tid, 'run_id': run, 'finsight_asset_revision': 0,
        'finsight_asset_memory': {'version': 0, 'body': 'Pinned preference: preserve all original units.'}}}
    async def execute():
        async with runtime.conversation_session_graph(config, SimpleNamespace(execution_runtime=object())) as graph:
            return await graph.ainvoke({'messages': [HumanMessage(content='Read the selected original source.') ]}, config=config)
    result = asyncio.run(execute())
    assert result['messages'][-1].content == 'Scripted delivery, no financial acceptance.'
    assert 'Pinned preference' in str(contexts[0]) and 'A later preference' not in str(contexts[0])
    assert 'Revenue 120' in str(contexts[1])
    assert TaskAssetUpdates(service.attachment_store.root).revision_for(tid, run) == 0
