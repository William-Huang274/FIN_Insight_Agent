import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents.middleware.types import ModelRequest

from test_asset_conversation import draft
from test_project_research_materials import WRITE
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.agent_runtime.working_memory_tools import native_memory_scope, execute_memory_tool
from sec_agent.agent_runtime.user_workpaper_context import human_revision_catalog


def test_project_navigation_original_edit_and_owner_recheck(tmp_path, monkeypatch):
    from apps.workbench.backend.api.v1.project_workpapers import build_project_workpapers_router
    client, service, calls, tid, workspace, project, ref = draft(tmp_path)
    client.app.include_router(build_project_workpapers_router(workspace.library.documents.root, service), prefix='/api/v1')
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH', str(tmp_path/'notes.sqlite'))
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_SEMANTIC', '0')
    memory = WorkingMemory(tmp_path/'notes.sqlite', owner='local-pilot', workspace=tid, actor='cash')
    saved = memory.save('现金流假设', 'Old working assumption; not evidence.')
    path = f'/api/v1/asset-workspace/projects/{project}/tasks'
    row = client.get(path).json()['items'][0]
    assert row['thread_id'] == tid and row['surface'] == 'conversations'
    thread = asyncio.run(service.sdk.threads.get(tid)); thread['status'] = 'busy'
    response = client.put(f'/api/v1/conversations/{tid}/working-notes', headers=WRITE,
        json={'note_id': saved['note_id'], 'version': 1, 'body': 'User correction: check period and unit before using the assumption.'})
    assert response.status_code == 200, response.text
    assert memory.read(saved['note_id'])['version'] == 2
    assert memory.read(saved['note_id'], version=1)['body'].startswith('Old')
    assert human_revision_catalog(memory)['items'][0]['user_version'] == 2
    rejected = memory.save('现金流假设', 'Stale agent overwrite.', 1)
    assert not rejected['saved']
    thread['metadata']['owner_id'] = 'bob'
    assert client.get(path).json()['items'] == []
    async def offline(_): raise OSError('private-host')
    service.sdk.threads.get = offline
    response = client.get(path)
    assert not response.json()['items'][0]['available'] and 'private-host' not in response.text
    assert not any(c[0] == 'run' for c in calls)


def test_each_audited_model_turn_receives_human_revision_locator(tmp_path, monkeypatch):
    from sec_agent.agent_runtime.case_review_agent import CaseModelAudit
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
    from tests.integration.fixtures.asset_conversation_script import ScriptedModel
    import json
    from pathlib import Path
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH', str(tmp_path/'notes.sqlite'))
    memory = WorkingMemory(tmp_path/'notes.sqlite', owner='alice', workspace='workspace', actor='cash')
    note = memory.save('Original financial assumption', 'Keep the exact 2025 USD source in the original record.')
    spec = json.loads(Path('configs/research/runtime/conversation.json').read_text())
    audit = CaseModelAudit(actor='cash', profile=DeepSeekModelProfile.model_validate(spec['profile']),
        basis=TokenBudgetBasis.model_validate_json(json.dumps(spec['budget'])), public_sink=lambda _:None, private_sink=lambda _:None)
    seen = []
    async def execute(request, *args):
        seen.append(deepcopy(request.system_message.content)); return SimpleNamespace()
    monkeypatch.setattr(audit, '_execute_model_call', execute)
    request = ModelRequest(model=ScriptedModel(responses=[]), messages=[HumanMessage(content='Continue this research.')],
                           system_message=SystemMessage(content='Original instructions'), tools=[], state={})
    async def run():
        with native_memory_scope('alice', 'workspace'):
            await audit.awrap_model_call(request, None)
            memory.save('Original financial assumption', 'A user correction with exact 2026 EUR scope.', 1, user_edit=True)
            await audit.awrap_model_call(request, None)
        with native_memory_scope('bob', 'workspace'):
            await audit.awrap_model_call(request, None)
    asyncio.run(run())
    assert seen[0] == 'Original instructions' and seen[2] == 'Original instructions'
    assert note['note_id'] in str(seen[1]) and 'user_version' in str(seen[1])
    assert '2026 EUR' not in str(seen[1])  # Locator, not a duplicate body in every request.
    read = execute_memory_tool('ReadWorkingNote', {'note_id': note['note_id'], 'version': 2}, {}, 'cash', owner='alice', workspace='workspace')
    assert '2026 EUR' in read['body']
    found = execute_memory_tool('SearchWorkingNotes', {'user_edits_only': True}, {}, 'cash', owner='alice', workspace='workspace')
    assert found['items'][0]['user_version'] == 2
    # Agent updates retain the historical human correction locator.
    memory.save('Original financial assumption', 'Agent incorporated user correction; still unverified.', 2)
    row = human_revision_catalog(memory)['items'][0]
    assert row['version'] == 3 and row['user_version'] == 2
