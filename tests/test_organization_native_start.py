"""First command admission, response loss and revocation; static native transport."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from test_java_research_intake import intake, request
from test_organization_native_drafts import organization, prepare
from sec_agent.agent_runtime.organization_native_contract import run_request
from sec_agent.agent_runtime.organization_native_runtime import admit


@pytest.fixture
def starting(organization, monkeypatch):
    s = organization
    with TestClient(s.intake.app()) as client:
        receipt = prepare(client, s)
        assert receipt.status_code == 200, receipt.text
    grant = deepcopy(s.grant)
    payload = {key:grant[key] for key in ('execution_id','project_id','manifest_digest','prepare_operation_id')}
    payload.update(contract_version='organization_native_start.v1', configuration_digest=receipt.json()['configuration_digest'],
                   stage='orientation', research_as_of=json.loads(grant['manifest_text'])['research_as_of']+'T12:00:00+08:00')
    grant.update(start_request=payload, start_operation_id=str(uuid4()), configuration_digest=payload['configuration_digest'],
                 start_request_digest='sha256:'+sha256(json.dumps(payload,separators=(',',':')).encode()).hexdigest())
    async def authority(actor, method, path, body=None):
        assert actor == 'oidc:alice' and method == 'GET' and path.endswith('/start-access')
        if s.state['status'] != 200:
            raise HTTPException(s.state['status'], 'revoked')
        return deepcopy(grant)
    monkeypatch.setattr('apps.workbench.backend.business_transport.space_business_request', authority)
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_START_ENABLED','1')
    original = s.intake.service.sdk.runs.create
    async def create(tid, graph, **kwargs):
        result = await original(tid, graph, **kwargs)
        result['thread_id'] = tid
        s.intake.runs[tid][-1]['thread_id'] = tid
        result.pop('config')
        s.intake.runs[tid][-1].pop('config')  # Matches the actual SDK Run schema.
        s.state['last_input'] = kwargs['input']
        assert kwargs['multitask_strategy'] == 'reject'
        if s.state['fault'] == 'lost_reply':
            raise httpx.ReadTimeout('persisted before loss')
        if s.state['fault'] == 'revoke_after_create':
            s.state['status'] = 404
        return result
    monkeypatch.setattr(s.intake.service.sdk.runs,'create',create)
    s.start_grant, s.start_body = grant, payload
    return s


def start(client, s):
    return request(client,'organization/start',s.start_body,s.start_grant['start_operation_id'])


def state(client, s):
    return request(client,f"organization/executions/{s.grant['execution_id']}/start-state?project_id={s.grant['project_id']}")


def test_start_pins_run_replays_and_revocation_precedes_cached_receipt(starting):
    s = starting
    with TestClient(s.intake.app()) as c:
        result = start(c,s)
        assert result.status_code == 200, result.text
        assert s.state['last_input']['research_stage'] == 'orientation'
        assert s.state['last_input']['question'] == s.grant['question']
        assert start(c,s).json() == result.json() == state(c,s).json()
        assert len(s.intake.runs[s.grant['execution_id']]) == 1
        s.state['status'] = 404
        assert start(c,s).status_code == state(c,s).status_code == 404
    s.state['status'] = 200
    with TestClient(s.intake.app()) as c:
        assert start(c,s).json() == result.json()
        assert len(s.intake.runs[s.grant['execution_id']]) == 1


@pytest.mark.parametrize('fault',['lost_reply','revoke_after_create'])
def test_uncertain_start_reconciles_without_new_run(starting,fault):
    s = starting
    s.state['fault'] = fault
    with TestClient(s.intake.app(),raise_server_exceptions=False) as c:
        assert start(c,s).status_code == (500 if fault == 'lost_reply' else 409)
        s.state.update(fault=None,status=200)
        assert start(c,s).json()['submission_status'] == 'unknown'
        assert state(c,s).status_code == 200
        assert len(s.intake.runs[s.grant['execution_id']]) == 1


@pytest.mark.parametrize('fault',['operation','config','thread','cutoff','stage','disabled'])
def test_invalid_start_does_not_dispatch(starting,monkeypatch,fault):
    s = starting
    if fault == 'operation': s.start_grant['start_operation_id'] = str(uuid4()) # also alter payload digest below
    elif fault == 'config': s.intake.threads[s.grant['execution_id']]['metadata']['configuration_digest'] = 'sha256:'+'a'*64
    elif fault == 'thread': s.intake.threads[s.grant['execution_id']]['metadata']['owner_id'] = 'oidc:alice'
    elif fault == 'cutoff': s.start_body['research_as_of'] = '2026-10-12'
    elif fault == 'stage': s.start_body['stage'] = 'full'
    else: monkeypatch.delenv('FINSIGHT_ORGANIZATION_START_ENABLED')
    with TestClient(s.intake.app()) as c:
        result = request(c,'organization/start',s.start_body,str(uuid4()) if fault=='operation' else s.start_grant['start_operation_id'])
        assert result.status_code in (409,503),result.text
        assert not s.intake.runs


@pytest.mark.parametrize('fault',['extra_run','run_operation','dispatch_digest'])
def test_reconcile_never_guesses_latest(starting,fault):
    s = starting
    with TestClient(s.intake.app()) as c:
        assert start(c,s).status_code == 200
        runs = s.intake.runs[s.grant['execution_id']]
        if fault == 'extra_run': runs.append(deepcopy(runs[0]))
        elif fault == 'run_operation': runs[0]['metadata']['organization_start']['start_operation_id'] = str(uuid4())
        else: runs[0]['metadata']['organization_dispatch_digest'] = 'sha256:'+'0'*64
        assert state(c,s).status_code == 409


@pytest.mark.parametrize('fault',[None,'run','config','checkpoint','authority'])
def test_native_admission_checks_actual_run_before_host_resources(starting,fault):
    s = starting
    grant = deepcopy(s.start_grant)
    tid = grant['execution_id']; thread = s.intake.threads[tid]
    args = run_request(thread,grant); rid = str(uuid4())
    grant['authorized_run_id'] = rid
    run = {'thread_id':tid,'run_id':rid,'status':'running',**args}
    async def get(t,r):
        assert (t,r)==(tid,rid)
        return run
    async def saved(t): return {'values':{'initialized':True} if fault == 'checkpoint' else {}}
    class Authority:
        run_id = rid
        def __call__(self):
            if fault == 'authority': raise ValueError('denied')
            return grant
    native = SimpleNamespace(runs=SimpleNamespace(get=get),threads=SimpleNamespace(get_state=saved))
    config = deepcopy(args['config'])
    if fault == 'run': run['metadata']['organization_start']['start_operation_id'] = str(uuid4())
    if fault == 'config': config['configurable']['finsight_execution']['mode'] = 'standard'
    if fault:
        with pytest.raises(ValueError): asyncio.run(admit(native,config,thread,Authority()))
    else:
        assert asyncio.run(admit(native,config,thread,Authority())) == grant


@pytest.mark.parametrize('fault',[None,'input','revoked','second_run','retrieval'])
def test_actual_native_factory_runs_scoped_orientation_only(starting,tmp_path,monkeypatch,fault):
    from pathlib import Path
    from sec_agent.agent_runtime import research_session_runtime as runtime
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionUnavailable
    from test_organization_orientation import static_orientation
    s = starting; grant = deepcopy(s.start_grant); tid = grant['execution_id']; rid = str(uuid4())
    thread = s.intake.threads[tid]; args = run_request(thread,grant)
    config = deepcopy(args['config']); config['configurable'].update(thread_id=tid,run_id=rid)
    grant['authorized_run_id'] = rid
    resource_grant = {key:grant[key] for key in ('contract_version','execution_id','thread_id','project_id','draft_id','organization_id','manifest_digest','status','native_execution_enabled','manifest_text','inputs')}
    state = {'revoked':False,'closed':False}
    requests = []
    def authority(self,path,payload):
        if state['revoked']: raise OrganizationExecutionUnavailable('static revoked')
        if path.endswith('/admit-start'):
            if fault == 'second_run': raise OrganizationExecutionUnavailable('different native run already claimed')
            assert payload['run_id'] == rid and payload['operation_id'] == grant['start_operation_id']
            return deepcopy(grant)
        assert path.endswith('/access')
        return deepcopy(resource_grant)
    monkeypatch.setattr(OrganizationExecutionAuthority,'request',authority)
    async def get_run(t,r): return {'thread_id':tid,'run_id':rid,'status':'running',**deepcopy(args)}
    async def get_thread(t): return deepcopy(thread)
    async def saved(t): return {'values':{}}
    async def close(): state['closed'] = True
    native = SimpleNamespace(runs=SimpleNamespace(get=get_run), threads=SimpleNamespace(get=get_thread,get_state=saved),
                             http=SimpleNamespace(client=SimpleNamespace(aclose=close)))
    monkeypatch.setattr('langgraph_sdk.get_client',lambda:native)
    monkeypatch.setattr('sec_agent.agent_runtime.agent_server_entry._require_langsmith_execution_environment',lambda _:None)
    settings = tmp_path/'settings.json'
    settings.write_text(json.dumps({'workbench_url':'https://workbench.example.test','audit_root':str(tmp_path/'audit'), 'research_library':str(tmp_path/'forbidden-library'),
        'conversation_fact_mart':str(tmp_path/'forbidden-facts')}))
    for key,value in {'FIN_REPO_ROOT':str(Path(__file__).resolve().parents[1]),'FINSIGHT_REPORT_SESSION_SETTINGS':str(settings),
        'FINSIGHT_RESEARCH_SESSION_ENABLED':'1','FINSIGHT_BUSINESS_API_URL':'http://127.0.0.1:9',
        'FINSIGHT_ORGANIZATION_RUNTIME_SECRET':'synthetic-runtime-secret-for-native-start-test',
        'FINSIGHT_ORGANIZATION_ASSETS_ROOT':str(s.intake.service.attachment_store.root.parent/'project-library'/'organization-assets'),
        'DEEPSEEK_API_KEY':'offline-not-a-key'}.items():monkeypatch.setenv(key,value)
    def forbidden(*a,**k):pytest.fail('organization native entry opened personal/public context')
    monkeypatch.setattr(runtime,'open_approved_data_composition',forbidden)
    monkeypatch.setattr('sec_agent.agent_runtime.user_context.user_context_prompt',forbidden)
    monkeypatch.setattr('sec_agent.agent_runtime.working_memory_tools.native_memory_scope',forbidden)
    monkeypatch.setattr('sec_agent.research_foundation.research_library.open_library',forbidden)
    def model(value):
        result=static_orientation(value,requests)
        if fault=='revoked':state['revoked']=True
        return result
    monkeypatch.setattr(runtime.DeepSeekStructuredAgentAdapter,'from_config',lambda **k:SimpleNamespace(lead_research_turn=model,specialist_model_turn=forbidden))
    if fault=='retrieval':
        from sec_agent.agent_runtime.organization_data_composition import OrganizationDataFactory
        def preparation_failure(self):
            raise OrganizationExecutionUnavailable('retrieval preparation failed before model access')
        monkeypatch.setattr(OrganizationDataFactory,'prepare_retrieval',preparation_failure)
    async def exercise():
        async with runtime.research_session_graph(config,SimpleNamespace(execution_runtime=True)) as graph:
            incoming = deepcopy(args['input'])
            if fault=='input':incoming['question']='A different unauthorized financial research question.'
            return await graph.ainvoke(incoming,config)
    if fault:
        with pytest.raises(Exception) as denied:
            asyncio.run(exercise())
        import traceback
        details = ''.join(traceback.format_exception(denied.value))
        assert ('organization_start_input_mismatch' if fault=='input' else 'OrganizationExecutionUnavailable') in details
        assert len(requests)==(1 if fault=='revoked' else 0)
    else:
        result=asyncio.run(exercise())
        assert result['phase']=='research_orientation_submitted' and len(requests)==4
        assert result['research_orientation']['semantic_acceptance']=='not_assessed'
        assert result['case_papers']==[]
        assert state['closed']
