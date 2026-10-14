"""Independent promotion command, frozen predecessor, unknown receipt and admission."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from test_java_research_intake import intake, request
from test_organization_native_drafts import organization
from test_organization_native_start import starting, start
from sec_agent.agent_runtime.organization_continuation_contract import baseline_digest, continuation_request
from sec_agent.agent_runtime.organization_native_runtime import admit


@pytest.fixture
def continuing(starting, monkeypatch):
    s = starting
    with TestClient(s.intake.app()) as c:
        first = start(c, s).json()
    tid = s.grant['execution_id']
    s.intake.runs[tid][0]['status'] = 'success'
    s.baseline = {'checkpoint': {'checkpoint_id': str(uuid4()), 'checkpoint_ns': '', 'thread_id': tid},
                  'next': [], 'tasks': [], 'values': {'initialized': True, 'phase': 'research_orientation_submitted',
                  'research_stage': 'orientation', 'question': s.grant['question'], 'orientation_run_id': first['run_id'],
                  'research_orientation': {'overview': 'Synthetic preliminary output'}, 'case_papers': [], 'research_tasks': []}}
    p = {k: s.start_body[k] for k in ('execution_id','project_id','manifest_digest','prepare_operation_id','configuration_digest','research_as_of')}
    p.update(contract_version='organization_native_continuation.v1',action='begin_research',previous_run_id=first['run_id'],
             checkpoint_id=s.baseline['checkpoint']['checkpoint_id'],state_digest=baseline_digest(s.baseline))
    s.continue_body = p
    s.continue_grant = {k: deepcopy(v) for k,v in s.start_grant.items() if not k.startswith('start_')}
    s.continue_grant.update(continuation_request=p,continuation_operation_id=str(uuid4()),
        continuation_request_digest='sha256:'+sha256(json.dumps(p,separators=(',',':')).encode()).hexdigest())
    async def authority(actor,method,path,body=None):
        assert actor == 'oidc:alice' and path.endswith('/continuation-access')
        if s.state['status'] != 200: raise HTTPException(s.state['status'],'revoked')
        return deepcopy(s.continue_grant)
    monkeypatch.setattr('apps.workbench.backend.organization_native_continuation.space_business_request',authority)
    async def state(t,**kw): return deepcopy(s.baseline)
    s.intake.service.sdk.threads.get_state = state
    s.usage = {'recorded_requests':1,'unknown_or_pending_requests':0,'partial_audit':False}
    monkeypatch.setattr('apps.workbench.backend.api.v1.report_sessions.public_run_usage',lambda *a:([],s.usage))
    return s


def promote(c,s):
    return request(c,'organization/continue',s.continue_body,s.continue_grant['continuation_operation_id'])


def reconcile(c,s):
    return request(c,f"organization/executions/{s.grant['execution_id']}/continuation-state?project_id={s.grant['project_id']}")


def test_promotion_once_and_revocation_before_receipt_replay(continuing):
    s=continuing;tid=s.grant['execution_id']
    with TestClient(s.intake.app()) as c:
        result=promote(c,s)
        assert result.status_code==200,result.text
        assert s.state['last_input']['research_stage']=='full'
        assert promote(c,s).json()==result.json()==reconcile(c,s).json()
        assert len(s.intake.runs[tid])==2
        s.state['status']=404
        assert promote(c,s).status_code==reconcile(c,s).status_code==404
    s.state['status']=200
    with TestClient(s.intake.app()) as c:
        assert promote(c,s).json()==result.json()
        assert len(s.intake.runs[tid])==2


@pytest.mark.parametrize('fault',['lost_reply','revoke_after_create'])
def test_uncertain_promotion_never_retries_transport(continuing,fault):
    s=continuing;s.state['fault']=fault
    with TestClient(s.intake.app(),raise_server_exceptions=False) as c:
        assert promote(c,s).status_code in (409,500)
        s.state.update(fault=None,status=200)
        assert promote(c,s).json()['submission_status']=='unknown'
        assert reconcile(c,s).status_code==200
        assert len(s.intake.runs[s.grant['execution_id']])==2


@pytest.mark.parametrize('fault',['checkpoint','values','pending','previous','not_complete','busy','unknown_usage','missing_usage','empty_audit','partial_audit','extra_run','config','operation'])
def test_changed_or_unknown_predecessor_never_dispatches(continuing,fault):
    s=continuing;tid=s.grant['execution_id']
    if fault=='checkpoint':s.baseline['checkpoint']['checkpoint_id']=str(uuid4())
    elif fault=='values':s.baseline['values']['report']={'title':'Unexpected'}
    elif fault=='pending':s.baseline['next']=['research']
    elif fault=='previous':s.intake.runs[tid][0]['run_id']=str(uuid4())
    elif fault=='not_complete':s.intake.runs[tid][0]['status']='error'
    elif fault=='busy':s.intake.threads[tid]['status']='busy'
    elif fault=='unknown_usage':s.usage['unknown_or_pending_requests']=1
    elif fault=='missing_usage':s.usage=None
    elif fault=='empty_audit':s.usage['recorded_requests']=0
    elif fault=='partial_audit':s.usage['partial_audit']=True
    elif fault=='extra_run':s.intake.runs[tid].append(deepcopy(s.intake.runs[tid][0]))
    elif fault=='config':s.intake.threads[tid]['metadata']['configuration_digest']='sha256:'+'b'*64
    else:s.continue_grant['continuation_operation_id']=str(uuid4())
    before=len(s.intake.runs[tid])
    with TestClient(s.intake.app()) as c:
        response=request(c,'organization/continue',s.continue_body,str(uuid4()) if fault=='operation' else s.continue_grant['continuation_operation_id'])
        assert response.status_code==409,response.text
        assert len(s.intake.runs[tid])==before


@pytest.mark.parametrize('fault',[None,'config','snapshot','run','previous_status'])
def test_native_admission_rechecks_continuation_before_host_resources(continuing,fault):
    s=continuing;grant=deepcopy(s.continue_grant);tid=grant['execution_id'];rid=str(uuid4())
    thread=s.intake.threads[tid];args=continuation_request(thread,grant);grant['authorized_run_id']=rid
    run={'thread_id':tid,'run_id':rid,'status':'running',**args}
    async def get(t,r):
        return deepcopy(run) if r==rid else {'run_id':r,'status':'error' if fault=='previous_status' else 'success'}
    async def saved(t):return deepcopy(s.baseline)
    class Authority:
        run_id=rid
        def __call__(self):return grant
    config=deepcopy(args['config'])
    if fault=='config':config['configurable']['finsight_organization_start']={}
    if fault=='snapshot':s.baseline['values']['question']='Changed question'
    if fault=='run':run['metadata']['organization_dispatch_digest']='bad'
    native=SimpleNamespace(runs=SimpleNamespace(get=get),threads=SimpleNamespace(get_state=saved))
    if fault:
        with pytest.raises(ValueError):asyncio.run(admit(native,config,thread,Authority()))
    else:assert asyncio.run(admit(native,config,thread,Authority()))==grant
