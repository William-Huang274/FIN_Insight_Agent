"""Opt-in real saved sources through the project BFF and native agent tools.

The model is scripted. This proves source/method delivery, not research quality.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from test_conversation_agent import ScriptedTools
from test_research_session_bff import _app
from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore


@pytest.mark.local_data_integration
@pytest.mark.skipif(not os.getenv('FIN_MULTISOURCE_MANIFEST'), reason='explicit saved public-source manifest required')
def test_saved_multisource_project_enters_task_and_native_tools(tmp_path):
    manifest = json.loads(Path(os.environ['FIN_MULTISOURCE_MANIFEST']).read_text(encoding='utf-8'))
    output = Path(os.environ['FIN_MULTISOURCE_OUTPUT'])
    output.mkdir(parents=True, exist_ok=False)
    app, service, _, _ = _app()
    service.attachment_store = TaskAttachmentStore(output/'attachments')
    library = ProjectLibrary(output/'project-library')
    project = str(uuid4())
    library.save('local-pilot', 0, {'projects': [{'id': project, 'name': manifest['title']}], 'assignments': {}, 'pinned': []})
    scope = library.scope('local-pilot', project)
    docs = []
    for source in manifest['sources']:
        body = Path(source['path']).read_bytes()
        assert hashlib.sha256(body).hexdigest() == source['sha256']
        doc = library.documents.add(scope, Path(source['path']).name, body)
        docs.append(doc)
    async def update(thread_id, *, metadata):
        row = await service.sdk.threads.get(thread_id)
        row['metadata'].update(metadata)
        return row
    service.sdk.threads.update = update
    response = TestClient(app).post('/api/v1/research-sessions', headers={'X-Workbench-Request': '1'}, json={
        'mode': 'research', 'question': manifest['question'], 'defer_start': True,
        'project_materials': {'project_id': project, 'document_ids': [d['document_id'] for d in docs]}})
    assert response.status_code == 200, response.text
    tid = response.json()['thread_id']
    materials = service.attachment_store.list(tid)
    assert len(materials) == len(docs)
    calls = [('get_research_method', {'method_id': 'finance'})]
    for source, doc in zip(manifest['sources'], materials):
        assert doc['project_origin']['project_id'] == project
        calls.append(('read_task_material', {'request': {'operation': 'search',
            'document_id': doc['document_id'], 'query': source['probe_query'], 'limit': 3}}))
    messages = [AIMessage(content='', tool_calls=[{'name': name, 'args': args, 'id': str(i), 'type': 'tool_call'}])
                for i, (name, args) in enumerate(calls)]
    messages.append(AIMessage(content='Synthetic source delivery check complete; no financial conclusions.'))
    graph = build_conversation_agent(model=ScriptedTools(responses=messages),
        grants=conversation_tools(thread_id=tid, attachment_store=service.attachment_store),
        permission_mode='request_standard', checkpointer=InMemorySaver(), model_calls=len(calls)+3, tool_calls=len(calls)+2)
    result = asyncio.run(graph.ainvoke({'messages': [HumanMessage(content=manifest['question'])]},
        {'configurable': {'thread_id': tid}, 'recursion_limit': 80}))
    replies = [m for m in result['messages'] if isinstance(m, ToolMessage)]
    assert len(replies) == len(calls) and all(m.status == 'success' for m in replies)
    assert all(m.artifact['items'] for m in replies[1:])
    readback = TaskAttachmentStore(output/'attachments')
    assert [d['document_id'] for d in readback.list(tid)] == [d['document_id'] for d in materials]
    report = {'project_id': project, 'thread_id': tid, 'materials': materials,
        'provider_calls': 0, 'model': 'scripted', 'scope': 'real source delivery, not financial acceptance',
        'tool_response_characters': [len(str(m.content)) for m in replies],
        'tool_artifacts': [m.artifact for m in replies[1:]]}
    (output/'readback.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
