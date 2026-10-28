"""Public root answer/note views preserve versions and recheck current rights."""
from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_java_research_intake import intake
from test_organization_native_drafts import organization
from test_organization_work_session import continuous
from sec_agent.agent_runtime.working_memory import WorkingMemory


@pytest.fixture
def delivery(continuous, monkeypatch, tmp_path):
    s = continuous
    tid = s.grant['execution_id']; run = str(uuid4()); s.cp = str(uuid4())
    s.root = f"/api/v1/organization-projects/{s.grant['project_id']}/research/{tid}"
    s.headers = {'Authorization': 'Bearer synthetic', 'X-Workbench-Request': '1'}
    monkeypatch.setattr('apps.workbench.backend.authentication.OIDCBackend.verify', lambda *a: 'oidc:viewer')
    s.values = {'messages': [
        {'type': 'human', 'content': 'My question'},
        {'type': 'ai', 'content': 'Visible answer', 'additional_kwargs': {'reasoning_content': 'private reasoning'}, 'tool_calls': [{'args': {'secret': 'hidden'}}]},
        {'type': 'human', 'content': 'Internal receipt', 'additional_kwargs': {'finsight_runtime_receipt': True}},
        {'type': 'tool', 'content': 'private tool'}, {'type': 'system', 'content': 'private instruction'}]}
    async def authority(project, execution):
        if s.state['status'] != 200: raise HTTPException(404, 'revoked')
        return {**s.start_grant, 'reader': 'oidc:viewer', 'run_id': run}
    monkeypatch.setattr('apps.workbench.backend.organization_research_reads.read_authority', authority)
    async def state(thread, **kw):
        assert thread == tid
        if kw: assert kw['checkpoint_id'] == s.cp
        return {'values': deepcopy(s.values), 'checkpoint': {'checkpoint_id': s.cp}}
    s.intake.service.sdk.threads.get_state = state
    path = tmp_path / 'memory.sqlite'
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH', str(path))
    s.memory = WorkingMemory(path, owner='organization:'+s.grant['organization_id'], workspace=tid, actor='research_partner')
    return s


def test_root_snapshot_does_not_expose_tool_arguments_reasoning_or_runtime_messages(delivery):
    s = delivery
    with TestClient(s.intake.app()) as c:
        response = c.get(s.root, headers=s.headers)
        assert response.status_code == 200, response.text
        assert response.json()['runtime_contract'] == 'on_demand.v1'
        assert response.json()['conversation'] == [{'role': 'user', 'content': 'My question'}, {'role': 'assistant', 'content': 'Visible answer'}]
        assert 'private' not in response.text and 'Internal receipt' not in response.text and 'hidden' not in response.text


def test_cutover_exposes_one_new_research_entry_and_keeps_history_readable(delivery):
    s = delivery
    with TestClient(s.intake.app()) as c:
        assert c.get('/api/v1/organization-research-capabilities', headers=s.headers).json() == {'on_demand': True}
        assert c.get('/api/v1/research-session-config', headers=s.headers).json()['fresh_research_enabled'] is False
        result = c.post('/api/v1/research-sessions', headers=s.headers,
                        json={'title': 'New report', 'question': 'Investigate this question', 'mode': 'research', 'defer_start': True})
        assert result.status_code == 409, result.text
        assert c.get(s.root, headers=s.headers).status_code == 200
    assert not s.intake.runs


def test_workpaper_reads_submitted_version_not_newer_candidate_and_is_scoped(delivery, monkeypatch):
    s = delivery
    first = s.memory.save('Working note', 'Submitted version')
    s.memory.save('Working note', 'Unsubmitted changes', base_version=first['version'])
    s.values['delivery'] = {'artifact_kind': 'workpaper', 'artifact_id': first['note_id'], 'artifact_version': first['version']}
    with TestClient(s.intake.app()) as c:
        response = c.get(s.root+'/workpaper', params={'checkpoint_id': s.cp}, headers=s.headers)
        assert response.status_code == 200, response.text
        assert response.json()['body'] == 'Submitted version' and response.json()['version'] == 1
        other = WorkingMemory(s.memory.path, owner=s.memory.owner, workspace=str(uuid4()), actor='research_partner').save('Other', 'Not authorized here')
        s.values['delivery']['artifact_id'] = other['note_id']
        assert c.get(s.root+'/workpaper', params={'checkpoint_id': s.cp}, headers=s.headers).status_code == 409
        s.values['delivery']['artifact_id'] = first['note_id']
        original = WorkingMemory.read
        def read_then_revoke(self, *a, **kw):
            result = original(self, *a, **kw); s.state['status'] = 404; return result
        monkeypatch.setattr(WorkingMemory, 'read', read_then_revoke)
        denied = c.get(s.root+'/workpaper', params={'checkpoint_id': s.cp}, headers=s.headers)
        assert denied.status_code == 404 and 'Submitted version' not in denied.text


def test_stop_closes_authority_before_native_parent_and_child_interrupts(delivery, monkeypatch):
    s = delivery; tid = s.grant['execution_id']; child = str(uuid4()); calls = []
    async def java(actor, method, path, body=None):
        assert path.endswith('/close') and method == 'POST'
        calls.append('closed'); return {'native_threads': [tid, child]}
    monkeypatch.setattr('apps.workbench.backend.organization_research_commands.space_business_request', java)
    async def runs(thread):
        assert calls[0] == 'closed'
        return [{'run_id': str(uuid4()), 'status': 'running'}, {'run_id': str(uuid4()), 'status': 'success'}]
    async def cancel(thread, run, **kw):
        calls.append(thread); assert kw == {'action': 'interrupt'}
        if thread == child: raise TimeoutError('cancel reply lost')
    s.intake.service.all_runs = runs; s.intake.service.sdk.runs.cancel = cancel
    with TestClient(s.intake.app()) as c:
        result = c.post(s.root+'/stop', headers=s.headers, json={})
        assert result.status_code == 200, result.text
        assert result.json() == {'execution_closed': True, 'native_stop_pending': [child], 'new_model_requests_authorized': False}
    assert calls == ['closed', tid, child]


def test_closed_execution_returns_read_only_control_without_masking_other_conflicts(delivery, monkeypatch):
    s = delivery
    from fastapi import HTTPException
    import apps.workbench.backend.organization_research_reads as reads
    original = reads.read_authority
    closed = [True]
    async def authority(*args):
        return {**await original(*args), 'execution_closed': closed[0]}
    async def java(*args, **kwargs):
        raise HTTPException(409, 'closed or another conflict')
    monkeypatch.setattr(reads, 'read_authority', authority)
    monkeypatch.setattr('apps.workbench.backend.organization_research_commands.space_business_request', java)
    with TestClient(s.intake.app()) as c:
        result = c.get(s.root + '/control', headers=s.headers)
        assert result.status_code == 200 and result.json() == {'can_operate': False, 'execution_closed': True}
        closed[0] = False
        assert c.get(s.root + '/control', headers=s.headers).status_code == 409
